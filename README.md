A tool for downloading and preparing RHEL-based and upstream Linux kernels.

## Usage

    ./rhel-kernel-get.py VERSION [--output-dir DIR] [--kabi]

Downloads and prepares the given version of the Linux kernel. If the version
contains the release part (e.g., `3.10.0-862.el7`), it downloads the RHEL
(CentOS) kernel, otherwise (e.g., `4.10`), it downloads the upstream kernel.

`--output-dir` specifies the output directory of the downloaded kernel.

Setting `--kabi` extracts the KABI whitelist (applicable to RHEL kernels only).

## Requirements

* kernel build dependencies: gcc, make, bison, flex, libelf-dev (`elfutils-libelf-devel`),
  bc, openssl (`openssl-devel`).
* cpio
* tar, xz, bzip2
* Python 3 packages from `requirements.txt`

Eg. on Fedora the requirements can be downloaded by following commands:

```sh
dnf install gcc make bison flex elfutils-libelf-devel bc openssl-devel cpio tar xz bzip2
pip install -r requirements.txt
```
