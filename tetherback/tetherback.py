#!/usr/bin/env python3
#
# Inspired by https://gist.github.com/inhies/5069663
#
# Currently backs up /data, /system, and /boot partitions
# Includes /data/media* by default, unlike TWRP (see issue #35)

import subprocess as sp
import os, sys, datetime, socket, time, argparse, re
from sys import stderr
from base64 import standard_b64decode as b64dec
from progressbar import ProgressBar, Percentage, FileTransferSpeed, DataSize
from tabulate import tabulate
from enum import Enum
from hashlib import md5
from collections import namedtuple, OrderedDict as odict

from .version import __version__
from .adb_wrapper import AdbWrapper
from .adb_stuff import *

adbxp = Enum('AdbTransport', 'tcp pipe_xo pipe_b64 pipe_bin')
PartInfo = namedtuple('PartInfo', 'partname devname partn size mountpoint fstype')
BackupPlan = namedtuple('BackupPlan', 'fn taropts')

please_report = """Please report this issue at https://github.com/dlenski/tetherback/issues
Please post the entire output from tetherback!"""

########################################

def parse_args(args=None):
    p = argparse.ArgumentParser(description='''Tool to create TWRP and nandroid-style backups of an Android device running TWRP recovery, using adb-over-USB, without touching the device's internal storage or SD card.''')
    p.version=__version__
    p.add_argument('--version', action='version')
    p.add_argument('-a', '--adb-path', dest='adb_path', default=None, help='Specify path to ADB binary')
    p.add_argument('-s', dest='specific', metavar='DEVICE_ID', default=None, help="Specific device ID (shown by adb devices). Default is sole USB-connected device.")
    p.add_argument('-o', '--output-path', default=".", help="Set optional output path for backup files.")
    p.add_argument('-N', '--nandroid', action='store_true', help="Make nandroid backup; raw images rather than tarballs for /system and /data partitions (default is TWRP backup)")
    p.add_argument('-0', '--dry-run', action='store_true', help="Just show the partition map and backup plan, then exit.")
    p.add_argument('-V', '--no-verify', dest='verify', default=True, action='store_false', help="Don't record and verify md5sum of backup files (default is to verify).")
    p.add_argument('-v', '--verbose', action='count', default=0)
    p.add_argument('-f', '--force', action='store_true', help="DANGEROUS! DO NOT USE! (Tries to proceed even if TWRP recovery is not detected.)")
    g = p.add_argument_group('Data transfer methods',
                             description="The default is --exec-out with adb v1.0.32 or newer, and --tcp with older versions. If you have problems, please try --base64 for a slow but reliable transfer method (and report issues at http://github.com/dlenski/tetherback/issues)")
    x = g.add_mutually_exclusive_group()
    x.add_argument('-t','--tcp', dest='transport', action='store_const', const=adbxp.tcp, default=None,
                   help="ADB TCP forwarding (fast, should work with any host OS, but prone to timing problems)")
    x.add_argument('-x','--exec-out', dest='transport', action='store_const', const=adbxp.pipe_xo,
                   help="ADB exec-out binary pipe (should work with any host OS, but only with newer versions of adb and TWRP)")
    x.add_argument('-6','--base64', dest='transport', action='store_const', const=adbxp.pipe_b64,
                   help="Base64 pipe (very slow, should work with any host OS)")
    x.add_argument('-P','--pipe', dest='transport', action='store_const', const=adbxp.pipe_bin,
                   help="ADB shell binary pipe (fast, but probably only works on Linux hosts)")
    g = p.add_argument_group('Backup contents')
    g.add_argument('-M', '--media', dest='media_deprecated', action='store_true', default=False, help="Include /data/media* in TWRP backup (Deprecated: /data/media* is included by default. Use --no-media to exclude.)")
    g.add_argument('-D', '--data-cache', action='store_true', default=False, help="Include /data/*-cache in TWRP backup")
    g.add_argument('-R', '--recovery', action='store_true', default=False, help="Include recovery partition in backup")
    g.add_argument('-C', '--cache', dest='cache', action='store_true', default=False, help="Include /cache partition in backup")
    g.add_argument('-U', '--no-userdata', dest='userdata', action='store_false', default=True, help="Omit /data partition from backup (implies --no-media)")
    g.add_argument('-E', '--no-media', dest='media', action='store_false', default=True, help="Omit /data/media* from TWRP backup")
    g.add_argument('-S', '--no-system', dest='system', action='store_false', default=True, help="Omit /system partition from backup")
    g.add_argument('-B', '--no-boot', dest='boot', action='store_false', default=True, help="Omit boot partition from backup")
    g.add_argument('-X', '--extra', action='append', metavar='NAME', default=[], help="Include extra partition (as a tarball if this partition is mountable and TWRP backup type is chosen, otherwise as raw image)")
    g.add_argument('--extra-raw', action='append', metavar='NAME', default=[], help="Include extra partition (always as raw image)")
    return p, p.parse_args(args)

def check_adb_version(p, adb):
    # check ADB version compatibility
    try:
        adbversions, adbversion = adb.get_version()
    except FileNotFoundError:
        p.error("could not call adb binary -- is it in your PATH?\n\thttp://developer.android.com/tools/help/adb.html")
    except (sp.CalledProcessError, RuntimeError):
        p.error("could not determine ADB version")

    if adbversion<(1,0,31):
        p.error(f"found ADB version {adbversions}, but version >= 1.0.31 is required")
    else:
        print(f"Found ADB version {adbversions}", file=stderr)

    return adbversion

def check_TWRP(p, adb, force=False):
    # check that device is booted into TWRP
    try:
        kernel = adb.check_output(('shell','uname -r')).strip()
    except sp.CalledProcessError:
        p.error(f"No device is connected via USB. adb returns an error:\n\n\t{' '.join(adb.adbcmd(('shell',)))}")
    print(f"Device reports kernel {kernel}", file=stderr)
    output = adb.check_output(('shell','twrp -v')).strip()
    m = re.search(r'TWRP version ((?:\d+.)+\d+)', output)
    if not m and force:
        print("********************")
        print("Device does not appear to be in TWRP recovery, but you specified --force")
        print("If you try to run a backup while booted in the Android OS:")
        print("  - You will probably get errors.")
        print("  - Even if the backup runs without error, it is likely to be corrupted")
        print(f"Unless you are developing or debugging {p.prog}, don't use this.")
        print("********************")
        if input("Really proceed (y/N)? ")[:1].lower() != 'y':
            raise SystemExit(1)
    elif not m:
        print(output)
        p.error("Device is not in TWRP; please boot into TWRP recovery and retry.")
    else:
        print(f"Device reports TWRP version {m.group(1)}", file=stderr)

def sensible_transport(transport, adbversion):
    if transport==adbxp.pipe_xo and adbversion<(1,0,32):
        print("WARNING: exec-out pipe (--exec-out) won't work with ADB version < 1.0.32; changing to TCP", file=stderr)
        return adbxp.tcp
    elif transport==adbxp.pipe_bin:
        if adbversion>=(1,0,32):
            print("WARNING: adb shell pipe (--pipe) not needed with ADB >= 1.0.32; changing to adb exec-out pipe", file=stderr)
            return adbxp.pipe_xo
        elif sys.platform.startswith('linux'):
            print("WARNING: adb shell pipe (--pipe) only works on Linux host; changing to TCP", file=stderr)
            return adbxp.tcp
    elif transport is None:
        if adbversion>=(1,0,32):
            print("Using default transfer method: adb exec-out pipe (--exec-out)", file=stderr)
            return adbxp.pipe_xo
        else:
            print("Using default transfer method: adb TCP forwarding (--tcp)", file=stderr)
            return adbxp.tcp
    return transport

def get_userdata_partinfo(fstab):
    for dev, info in fstab.items():
        if info[0] == '/data':
            return { 'dev': dev.split('/')[-1], 'mnt': info[0], 'fs': info[1] }
    return None

def build_partmap(adb, mmcblks=None, fstab='/etc/fstab'):
    # build partition map
    partmap = odict()
    fstab = fstab_dict(adb, fstab)
    userdata_partinfo = get_userdata_partinfo(fstab)

    if mmcblks is None:
        # issue #29: not all TWRP busybox builds have the ls -1 (single-column) option
        mmcblks = adb.check_output(('shell','cd /sys/block; ls -d mmcblk*')).split()
    for mmcblk in mmcblks:
        d = uevent_dict(adb, f'/sys/block/{mmcblk}/uevent')
        nparts = int(d.get('NPARTS',0))
        print(f"Reading partition map for {mmcblk} ({nparts} partitions)...", file=stderr)
        pbar = ProgressBar(max_value=nparts, widgets=['  partition map: ', Percentage()]).start()
        for ii in range(1, nparts+1):
            d = uevent_dict(adb, f'/sys/block/{mmcblk}/{mmcblk}p{ii}/uevent')
            if {'DEVNAME','PARTN'} - set(d):
                print(f"WARNING: partition {mmcblk}p{ii} is missing DEVNAME or PARTN field, skipping\n{please_report}", file=stderr)
                continue

            devname, partn = d['DEVNAME'], int(d['PARTN'])
            assert partn==ii                          # mmcblk0p23/uevent must have PARTN=23
            assert devname==f'{mmcblk}p{partn}' # mmcblk0p23/uevent must have DEVNAME=mmcblk0p23

            size = int(adb.check_output(('shell',f'cat /sys/block/{mmcblk}/{mmcblk}p{ii}/size')))
            mountpoint, fstype = fstab.get(f'/dev/block/{devname}', (None, None))

            if 'PARTNAME' not in d:
                print(f"WARNING: partition {mmcblk}p{ii} has no PARTNAME in its uevent file\n{please_report}", file=stderr)
                partname = devname
            else:
                # some devices have uppercase names, see #14
                partname = d['PARTNAME'].lower()

            # some devices apparently use non-standard partition names, though standard mount points, see #18
            if partname=='system' or mountpoint=='/system':
                standard = 'system'
            elif partname=='userdata' or mountpoint=='/data':
                standard = 'userdata'
            elif partname=='cache' or mountpoint=='/cache':
                standard = 'cache'
            else:
                standard = partname

            if partname == 'userdata' and mountpoint == None and userdata_partinfo != None:
                # User data encrypted, get mountable device from fstab
                devname = userdata_partinfo['dev']
                mountpoint = userdata_partinfo['mnt']
                fstype = userdata_partinfo['fs']

            partmap[standard] = PartInfo(partname, devname, partn, size, mountpoint, fstype)
            pbar.update(ii)
        else:
            pbar.finish()
    else:
        return partmap

def plan_backup(args, partmap):
    # Build table of partitions requested for backup
    if args.nandroid:
        rp = args.extra + args.extra_raw + [x for x in ('boot','recovery','system','userdata','cache') if getattr(args, x)]
        plan = odict((p,BackupPlan(f'{p}.emmc.gz', None)) for p in rp)
    else:
        # Figure out which of the --extra partitions can't actually be mounted and exile them to --extra-raw
        extra_raw = args.extra_raw
        extra_mount = []
        for p in args.extra:
            (extra_mount if p in partmap and partmap[p].fstype else extra_raw).append(p)

        rp = extra_raw + [x for x in ('boot','recovery') if getattr(args, x)]
        plan = odict((p,BackupPlan(f'{p}.emmc.win', None)) for p in rp)
        mp = extra_mount + [x for x in ('cache','system') if getattr(args, x)]
        plan.update((p,BackupPlan(f'{p}.{partmap[p].fstype}.win', '-p')) for p in mp)

        if args.userdata:
            data_omit = []
            if not args.media: data_omit.append("media*")
            if not args.data_cache: data_omit.append("*-cache")
            plan['userdata'] = BackupPlan('data.ext4.win', '-p'+''.join(f' --exclude="{x}"' for x in data_omit))
    return plan

def show_partmap_and_plan(partmap, plan):
    print("\nPartition map:\n")
    print(tabulate( [[ p.devname, p.partname + (f' (standard {standard})' if p.partname!=standard else ''), p.size//2, p.mountpoint, p.fstype] for standard, p in partmap.items() ]
                    +[[ '', 'Total:', sum(p.size//2 for p in partmap.values()), '', '' ]],
                    [ 'BLOCK DEVICE','PARTITION NAME','SIZE (KiB)','MOUNT POINT','FSTYPE' ] ))

    print("\nBackup plan:\n")
    print(tabulate( [[standard, fn,  "gzipped raw image" if taropts is None else "tar -cz "+taropts] for standard, (fn, taropts) in plan.items() ],
                    [ 'PARTITION NAME','FILENAME','FORMAT' ] ))
    print()

def create_backupdir(args, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.now()

    btype = 'nandroid' if args.nandroid else 'twrp'
    backupdir = os.path.join(args.output_path, btype + '-backup-' + timestamp.strftime('%Y-%m-%d--%H-%M-%S'))

    if not os.path.exists(args.output_path):
       os.mkdir(args.output_path)
    os.mkdir(backupdir)
    return backupdir

def backup_partition(adb, pi, bp, transport, backupdir, verify=True):
    # Create a FIFO for device-side md5 generation
    if verify:
        adb.check_call(('shell','rm -f /tmp/md5in /tmp/md5out 2> /dev/null; mknod /tmp/md5in p'))

    if bp.taropts:
        if not pi.mountpoint:
            raise RuntimeError(f"{pi.devname}: don't know how to mount this partition")
        print(f"Saving tarball of {pi.devname} (mounted at {pi.mountpoint}), {pi.size // 2048} MiB uncompressed...")
        fstype = really_mount(adb, '/dev/block/'+pi.devname, pi.mountpoint)
        if not fstype:
            raise RuntimeError(f'{pi.partname}: could not mount {pi.mountpoint}')
        if fstype != pi.fstype:
            raise RuntimeError(f'{pi.partname}: expected {pi.fstype} filesystem, but found {fstype}')
        cmdline = f"tar -czC {pi.mountpoint} {bp.taropts or ''} . 2> /dev/null"
    else:
        print(f"Saving partition {pi.partname} ({pi.devname}), {pi.size // 2048} MiB uncompressed...")
        if not really_umount(adb, '/dev/block/'+pi.devname, pi.mountpoint):
            raise RuntimeError(f'{pi.partname}: could not unmount {pi.mountpoint}')
        cmdline = f'dd if=/dev/block/{pi.devname} 2> /dev/null | gzip -f'

    if verify:
        cmdline = f'md5sum /tmp/md5in > /tmp/md5out & {cmdline} | tee /tmp/md5in'
        localmd5 = md5()

    if transport == adbxp.pipe_bin:
        # need stty -onlcr to make adb-shell an 8-bit-clean pipe: http://stackoverflow.com/a/20141481/20789
        child = adb.pipe_out(('shell','stty -onlcr && '+cmdline))
        block_iter = iter(lambda: child.stdout.read(65536), b'')
    elif transport == adbxp.pipe_b64:
        # pipe output through base64: excruciatingly slow
        child = adb.pipe_out(('shell',cmdline+'| base64'))
        block_iter = iter(lambda: b64dec(b''.join(child.stdout.readlines(65536))), b'')
    elif transport == adbxp.pipe_xo:
        # use adb exec-out, which is
        # (a) only available with newer versions of adb on the host, and
        # (b) only works with newer versions of TWRP (works with 2.8.0 for @kerlerm)
        # https://plus.google.com/110558071969009568835/posts/Ar3FdhknHo3
        # https://android.googlesource.com/platform/system/core/+/5d9d434efadf1c535c7fea634d5306e18c68ef1f/adb/commandline.c#1244
        child = adb.pipe_out(('exec-out',cmdline))
        block_iter = iter(lambda: child.stdout.read(65536), b'')
    else:
        port = really_forward(adb, 5600+pi.partn, 5700+pi.partn)
        if not port:
            raise RuntimeError('could not ADB-forward a TCP port')
        child = adb.pipe_out(('shell',cmdline + f'| nc -l -p{port} -w3'))

        # FIXME: need a better way to check that socket is ready to transmit
        time.sleep(1)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('localhost', port))
        block_iter = iter(lambda: s.recv(65536), b'')

    pbwidgets = [f'  {bp.fn}: ', Percentage(), ' ', FileTransferSpeed(), ' ', DataSize() ]
    pbar = ProgressBar(max_value=pi.size*512, widgets=pbwidgets).start()

    with open(os.path.join(backupdir, bp.fn), 'wb') as out:
        for block in block_iter:
            out.write(block)
            if verify:
                localmd5.update(block)
            pbar.update(min(out.tell(), pbar.max_value))
        else:
            pbar.max_value = out.tell() or pbar.max_value # need to adjust for the smaller compressed size
            pbar.finish()

    if verify:
        devicemd5 = adb.check_output(('shell','cat /tmp/md5out && rm -f /tmp/md5in /tmp/md5out')).strip().split()[0]
        localmd5 = localmd5.hexdigest()
        if devicemd5 != localmd5:
            raise RuntimeError(f"md5sum mismatch (local {localmd5}, device {devicemd5})")
        with open(os.path.join(backupdir, bp.fn+'.md5'), 'w') as md5out:
            print(f'{localmd5} *{bp.fn}', file=md5out)

    child.wait()
    if transport==adbxp.tcp:
        s.close()
        if not really_unforward(adb, port):
            raise RuntimeError(f'could not remove ADB-forward for TCP port {port}')

########################################

def main(args=None):
    p, args = parse_args(args)

    # warn about deprecated options, if passed on command line
    if args.media_deprecated:
        p.error("-M/--media is deprecated. /data/media* will be included by default. Use -E/--no-media to exclude.")

    adb = AdbWrapper(args.adb_path or 'adb', ('-s',args.specific) if args.specific else ('-d',), debug=(args.verbose > 1))

    print(f'{p.prog} v{p.version}', file=stderr)

    # check adb version, and TWRP recovery
    adbversion = check_adb_version(p, adb)
    args.transport = sensible_transport(args.transport, adbversion)
    check_TWRP(p, adb, args.force)

    # build partition map and backup plan
    partmap = build_partmap(adb)
    plan = plan_backup(args, partmap)
    missing = set(plan) - set(partmap)

    # print partition map and backup explanation
    if args.dry_run or missing or args.verbose > 0:
        show_partmap_and_plan(partmap, plan)

    if missing & {'cache','system','data','boot'}:
        p.error(f"Standard partitions were requested for backup, but not found in the partition map: {', '.join(missing)}\n{please_report}")
    elif missing:
        p.error(f"These non-standard partitions were requested for backup, but not found in the partition map: {', '.join(missing)}")

    if args.dry_run:
        p.exit()

    # create backup directory
    backupdir = create_backupdir(args)
    print(f"Saving backup images in {backupdir}/ ...", file=stderr)

    # Okay, now it's time to actually... back up the partitions!
    for standard, bp in plan.items():
        backup_partition(adb, partmap[standard], bp, args.transport, backupdir, args.verify)

    print("Backup complete.", file=stderr)
