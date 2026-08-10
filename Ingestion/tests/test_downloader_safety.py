import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from Dataset_Downloader.download_pmc_packages import extract_package


class DownloaderSafetyTests(unittest.TestCase):
    def test_rejects_path_traversal_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "unsafe.tar.gz"
            with tarfile.open(archive, "w:gz") as handle:
                info = tarfile.TarInfo("../outside.txt")
                payload = b"unsafe"
                info.size = len(payload)
                handle.addfile(info, io.BytesIO(payload))
            self.assertFalse(extract_package(archive, root / "output"))
            self.assertFalse((root / "outside.txt").exists())


if __name__ == "__main__":
    unittest.main()
