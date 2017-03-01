# tetherback

Tools to create TWRP and nandroid-style backups of an Android device via a USB connection,
without using the device's internal storage or SD card.

To guarantee against backup corruption during transfer, it generates
[md5sums](https://en.wikipedia.org/wiki/md5sum) of the backup files on
the device and then verifies that they match on the host.

**WARNING:** This is a work in progress. I have personally tested it on the
following device/recovery/host combinations…

| Device | Codename | TWRP recovery | `adb` | Host OS | Comments |
|--------|----------|---------------|-------|---------|----------|
| [LG/Google Nexus 5](http://wikipedia.org/wiki/Nexus_5) | hammerhead | [v2.8.5-0](http://teamw.in/site/update/2015/02/12/twrp-2.8.5.0-released.html) | v1.0.32 | Ubuntu amd64 |**`adb exec-out` does not work** |
| [LG/Google Nexus 5](http://wikipedia.org/wiki/Nexus_5) | hammerhead | [v3.0.0-0](https://twrp.me/site/update/2016/02/05/twrp-3.0.0-0-released.html) | v1.0.31 | Ubuntu amd64 | working |
| [LG/Google Nexus 5](http://wikipedia.org/wiki/Nexus_5) | hammerhead | [v3.0.0-0](https://twrp.me/site/update/2016/02/05/twrp-3.0.0-0-released.html) | v1.0.32 | Ubuntu amd64 | working |
| [LG/Google Nexus 5](http://wikipedia.org/wiki/Nexus_5) | hammerhead | [v3.0.2-0](https://twrp.me/site/update/2016/04/05/twrp-3.0.2-0-released.html) | v1.0.32 | Ubuntu amd64 | working |
| [Samsung Galaxy S4](https://en.wikipedia.org/wiki/Samsung_Galaxy_S4) L720T | jfltespr | [v3.0.2-0](https://twrp.me/site/update/2016/04/05/twrp-3.0.2-0-released.html) | v1.0.32 | Ubuntu amd64 | working |
| [Moto G4 Play](https://en.wikipedia.org/wiki/Moto_G4) | harpia | [v3.0.2-r5](https://twrp.me/site/update/2016/04/05/twrp-3.0.2-0-released.html) | v1.0.32 | Ubuntu amd64 | working |

Other users have reported success—and
[issues](https://github.com/dlenski/tetherback/issues?q=is%3Aissue+is%3Aclosed)
☺—with other devices, including
[`picassowifi`](https://wiki.cyanogenmod.org/w/Picassowifi_Info),
[`cancro`](https://wiki.cyanogenmod.org/w/Cancro_Info),
[`Z00T`](https://wiki.cyanogenmod.org/w/Z00T_Info); and other operating
systems, various versions of Windows and Mac OS X.

## Requirements and installation

tetherback requires Python 3.3+. In addition, it depends on:

* [TWRP recovery](https://twrp.me/) installed on your rooted Android device
* [`adb`](https://en.wikipedia.org/wiki/Android_software_development#ADB) (Android Debug Bridge) command-line tools
* `progressbar2` and `tabulate` packages from PyPI (fetched automatically during `pip install`; see below)

Install with `pip3` to automatically fetch Python dependencies. (Note that on most systems, `pip` invokes
the Python 2.x version, while `pip3` invokes the Python 3.x version.)

```
# Install latest development version
$ pip3 install https://github.com/dlenski/tetherback/archive/HEAD.zip

# Install a tagged release
# (replace "RELEASE" with one of the tag/release version numbers on the "Releases" page)
$ pip3 install https://github.com/dlenski/tetherback/archive/RELEASE.zip
```

## Usage

Boot your device into TWRP recovery and connect it via USB. Ensure that it's visible to `adb`:

```bash
$ adb devices
List of devices attached
0123deadbeaf5f5f	recovery
```

* Make a TWRP-style backup over ADB. This saves a gzipped image of the
  `boot` partition as `boot.emmc.win`, and saves the *contents* of the
  `/system` and `/data` partitions as tarballs named `system.ext4.win`
  and `data.ext4.win`:

    ```bash
    $ tetherback
    tetherback v0.8
    Found ADB version 1.0.32
    Using default transfer method: adb exec-out pipe (--exec-out)
    Device reports kernel 3.4.0-bricked-hammerhead-twrp-g7b77eb4
    Device reports TWRP version 3.0.0-0
    Reading partition map for mmcblk0 (29 partitions)...
      partition map: 100%
    Reading partition map for mmcblk0rpmb (0 partitions)...
      partition map: 100%
    Saving backup images in ./twrp-backup-2016-07-03--14-53-29/ ...
    Saving partition boot (mmcblk0p19), 22 MiB uncompressed...
      boot.emmc.win: 100%   4.0 MiB/s  16.3 MiB
    Saving tarball of mmcblk0p25 (mounted at /system), 1024 MiB uncompressed...
      system.ext4.win: 100%   2.5 MiB/s 299.7 MiB
    Saving tarball of mmcblk0p28 (mounted at /data), 13089 MiB uncompressed...
      data.ext4.win: 100%   2.0 MiB/s 804.0 MiB
    ```

* Make a "nandroid"-style backup over ADB. This saves gzipped images
  of the partitions labeled `boot`, `system`, and `userdata` (named
  `<label>.img.gz`):

    ```bash
    $ tetherback -N
    tetherback v0.8
    Found ADB version 1.0.32
    Using default transfer method: adb exec-out pipe (--exec-out)
    Device reports kernel 3.4.0-bricked-hammerhead-twrp-g7b77eb4
    Device reports TWRP version 3.0.0-0
    Reading partition map for mmcblk0 (29 partitions)...
      partition map: 100% Time: 0:00:03
    Reading partition map for mmcblk0rpmb (0 partitions)...
      partition map: 100%
    Saving backup images in nandroid-backup-2016-07-03--18-15-03/ ...
    Saving partition boot (mmcblk0p19), 22 MiB uncompressed...
      mmcblk0p19: 100%   3.07 MB/s  16.3 MiB
    Saving partition system (mmcblk0p25), 1024 MiB uncompressed...
      mmcblk0p25: 100%   1.76 MB/s  343.7 MiB
    Saving partition userdata (mmcblk0p28), 13089 MiB uncompressed...
      mmcblk0p28: 100%   1.80 MB/s  6.4 GiB
    ```

### Additional options

* Extra partitions can be included with the `-X`/`--extra` and `--extra-raw`
  options; for example, `-X modemst1 -X modemst2` to backup the
  [Nexus 5 EFS partitions](http://forum.xda-developers.com/google-nexus-5/development/modem-nexus-5-flashable-modems-efs-t2514095).

    * With `--extra-raw`, the extra partition will *always* be saved as a raw image, rather than as a tarball, even if it is a
      mountable filesystem and tetherback is run in TWRP backup mode.

* The partition map and backup plan will be printed with
  `-v`/`--verbose` (or use `-0`/`--dry-run` to **only** print it, and
  skip the actual backup). For example, the following partition map
  and backup plan will be shown for a Nexus 5 with the standard
  partition layout:

    ```
    BLOCK DEVICE    PARTITION NAME      SIZE (KiB)  MOUNT POINT    FSTYPE
    --------------  ----------------  ------------  -------------  --------
    mmcblk0p1       modem                    65536
    ...
    mmcblk0p19      boot                     22528
    ...
    mmcblk0p25      system                 1048576  /system        ext4
    ...
    mmcblk0p28      userdata              13404138  /data          ext4
    mmcblk0p29      grow                         5
                    Total:                15388143

    PARTITION NAME    FILENAME         FORMAT
    ----------------  ---------------  -------------------------------------------------
    boot              boot.emmc.win    gzipped raw image
    system            system.ext4.win  tar -cz -p
    userdata          data.ext4.win    tar -cz -p --exclude="media*" --exclude="*-cache"
    ```

* Additional options allow exclusion or inclusion of standard partitions:

    ```
    -M, --media           Include /data/media* in TWRP backup (deprecated: default behavior)
    -D, --data-cache      Include /data/*-cache in TWRP backup
    -R, --recovery        Include recovery partition in backup
    -C, --cache           Include /cache partition in backup
    -U, --no-userdata     Omit /data partition from backup (implies --no-media)
    -E, --no-media        Omit /data/media* from TWRP backup
    -S, --no-system       Omit /system partition from backup
    -B, --no-boot         Omit boot partition from backup
    ```

## Motivation

I've been frustrated by the fact that all the Android recovery backup
tools save their backups _on a filesystem on the device itself_.

* [TWRP recovery](https://twrp.me/)
  ([code](https://github.com/omnirom/android_bootable_recovery))
  creates a mixture of raw partition images and tarballs, and **stores
  the backups on the device itself.**
* Same with [CWM recovery](http://clockworkmod.com/rommanager) , which
  creates nandroid-style backup images (just raw partition images) and
  again **stores them on the device itself.**

This is problematic for several reasons:

1. Most modern Android smartphones don't have a microSD card slot.
2. There may not be enough space on the device's own filesystem to back up its own contents.
3. Getting the large backup files off of the device requires an extra, slow transfer step.

Clearly I'm not the only one with this problem:

* http://android.stackexchange.com/questions/64354/how-to-do-a-full-nandroid-backup-via-pc
* http://android.stackexchange.com/questions/47975/is-there-a-way-to-do-nandroid-backup-directly-to-pc-and-then-restore-it-directly

I found that [**@inhies**](https://github.com/inhies) had already
created a shell script to do a TWRP-style backup over USB
([Gist](https://gist.github.com/inhies/5069663)) and decided to try to
put together a more polished version of this.

## Issues

One of the very annoying issues with `adb` is that
[`adb shell` is not 8-bit-clean](http://stackoverflow.com/questions/13578416):
line endings in the input and output get mangled, so it cannot easily
be used to pipe binary data to and from the device. The common
workaround for this is to use TCP forwarding and `netcat` (see
[this answer on StackOverflow](http://stackoverflow.com/a/34216105/20789)),
but this is more cumbersome to code, and prone to strange timing
issues. There is a better way to make the output pipe 8-bit-clean, by
changing the terminal settings
([another StackOverflow answer](http://stackoverflow.com/a/20141481/20789)),
though apparently it does not work with Windows builds of `adb`.

*By default*, tetherback uses TCP forwarding with older versions of `adb`, and an `exec-out` binary pipe with newer versions (1.0.32+).
If you have problems, please try
`--base64` for a slow but reliable transfer method, and please
[report any data corruption issues](http://github.com/dlenski/tetherback/issues). If
your host OS is Linux, `--pipe` should be faster and more reliable.

  ```
  -t, --tcp             ADB TCP forwarding (fast, should work with any host
                        OS, but prone to timing problems)
  -x, --exec-out        ADB exec-out binary pipe (should work with any host
                        OS, but only with newer versions of adb and TWRP)
  -6, --base64          Base64 pipe (very slow, should work with any host OS)
  -P, --pipe            Binary pipe (fast, but probably only works
                        on Linux hosts)
  ```


## License

GPL v3 or newer
