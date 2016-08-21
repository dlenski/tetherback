#!/usr/bin/env python3
#
# The backup-restoration counterpart to tetherback

from progressbar import ProgressBar, Percentage, FileTransferSpeed, DataSize
from hashlib import md5

from .adb_wrapper import AdbWrapper, PIPE
from .adb_stuff import *

from .tetherback import adbxp, PartInfo, BackupPlan, please_report

from .tetherback import check_adb_version, check_TWRP, sensible_transport

def restore_partition(adb, pi, bp, transport, verify=True):
    # Create a FIFO for device-side md5 generation
    if verify:
        adb.check_call(('shell','rm -f /tmp/md5in /tmp/md5out 2> /dev/null; mknod /tmp/md5in p'))

    if bp.taropts:
        print("Restoring tarball of %s (mounted at %s), %d MiB uncompressed..." % (pi.devname, pi.mountpoint, pi.size/2048))
        fstype = really_mount(adb, '/dev/block/'+pi.devname, pi.mountpoint, mode='rw')
        if not fstype:
            raise RuntimeError('%s: could not mount %s' % (pi.partname, pi.mountpoint))
        if fstype != pi.fstype:
            raise RuntimeError('%s: expected %s filesystem, but found %s' % (pi.partname, pi.fstype, fstype))
        cmdline = 'tar -xzC %s %s . 2> /dev/null' % (pi.mountpoint, bp.taropts or '')
    else:
        print("Restoring image of partition %s (%s), %d MiB uncompressed..." % (pi.partname, pi.devname, pi.size/2048))
        if not really_umount(adb, '/dev/block/'+pi.devname, pi.mountpoint):
            raise RuntimeError('%s: could not unmount %s' % (pi.partname, pi.mountpoint))
        cmdline = 'gunzip -f | dd of=/dev/block/%s 2> /dev/null' % pi.devname

    if verify:
        vchild = adb.pipe(('shell','md5sum /tmp/md5in > /tmp/md5out'))
        cmdline = 'tee /tmp/md5in | %s' % cmdline
        localmd5 = md5()

    if transport in (adbxp.pipe_bin, adbxp.pipe_b64):
        # as far as I can tell, there's no way to make adb-shell into an input pipe at all
        raise RuntimeError('no support for --pipe or --base64 transports for restore')
    elif transport == adbxp.pipe_xo:
        # use adb exec-in, which is
        # (a) only available with newer versions of adb on the host, and
        # (b) only works with newer versions of TWRP (works with 3.0.0 for me)
        child = adb.pipe(('exec-in',cmdline), stdin=PIPE)
        block_dest = child.stdin
    else:
        # FIXME: can we use adb-reverse for this?
        # http://stackoverflow.com/a/31944432/20789
        raise RuntimeError('no support for --tcp transport for restore')

    pbwidgets = ['  %s: ' % bp.fn, Percentage(), ' ', FileTransferSpeed(), ' ', DataSize() ]
    pbar = ProgressBar(max_value=pi.size*512, widgets=pbwidgets).start()

    with open(bp.fn, 'rb') as inp:
        block_iter = iter(lambda: inp.read(65536), b'')
        for block in block_iter:
            block_dest.write(block)
            if verify:
                localmd5.update(block)
            pbar.update(inp.tell())
        else:
            block_dest.close()
            pbar.max_value = inp.tell() or pbar.max_value # need to adjust for the smaller compressed size
            pbar.finish()
            child.wait()

    if verify:
        vchild.wait()
        devicemd5 = adb.check_output(('shell','cat /tmp/md5out && rm -f /tmp/md5in /tmp/md5out')).strip().split()[0]
        localmd5 = localmd5.hexdigest()
        if devicemd5 != localmd5:
            raise RuntimeError("md5sum mismatch (local %s, device %s)" % (localmd5, devicemd5))
