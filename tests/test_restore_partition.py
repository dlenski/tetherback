#!/usr/bin/env python3
from tempfile import NamedTemporaryFile
from tetherback import tetherrestore as R
from gzip import compress

with NamedTemporaryFile(delete=False) as f:
    f.write(compress(open('/dev/urandom','rb').read(512000)))
    size = f.tell()

print(f.name, size)

bp=R.BackupPlan(fn=f.name, taropts=None)
pi=R.PartInfo(partname='test', devname='../../tmp/test.bin', partn=None, size=size/512, mountpoint=None, fstype=None)
adb=R.AdbWrapper(debug=True)

R.restore_partition(adb, pi, bp, R.adbxp.pipe_xo)
