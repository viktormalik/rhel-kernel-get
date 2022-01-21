#! /usr/bin/env python3
"""
Script for downloading and preparing RHEL-based and upstream Linux kernels.
Steps:
 - download kernel
 - configure kernel
 - for RHEL kernels, optionally extract KABI whitelist
"""

from argparse import ArgumentParser
from distutils.version import StrictVersion
from progressbar import ProgressBar, Percentage, Bar
from socket import gethostbyname, error as socket_error
from subprocess import check_call, check_output, Popen, PIPE, \
    CalledProcessError
from tempfile import mkdtemp
from urllib.request import urlretrieve
import os
import re
import shutil

# Progress bar for downloading
pbar = None

# Custom build flags
CFLAGS = "-Wno-error=attributes -Wno-error=restrict"
EXTRA_CFLAGS = "-Wno-error=restrict -fno-pie -no-pie"
LDFLAGS = "-no-pie"

def show_progress(count, block_size, total_size):
    """Showing progress of downloading."""
    global pbar
    if pbar is None:
        pbar = ProgressBar(maxval=total_size, widgets=[Percentage(), Bar()])
        pbar.start()

    downloaded = count * block_size
    if downloaded < total_size:
        pbar.update(downloaded)
    else:
        pbar.finish()
        pbar = None


def call_and_print(command):
    """Print command to stdout and call it."""
    print("  {}".format(" ".join(command)))
    check_call(command, stdout=None, stderr=None)


def get_config_file(version):
    """
    Get the name of the default config file.
    Currently, the one for x86_64 is taken.
    """
    configfile_options = [
        "kernel-x86_64.config",
        "kernel-{}-x86_64.config".format(version.split("-")[0])
    ]
    for configfile in configfile_options:
        if os.path.isfile(configfile):
            return os.path.abspath(configfile)
    return None


def get_kabi_file(version, kabi_filenames):
    for filename in kabi_filenames:
        if os.path.isfile(filename):
            return filename
    """Get the name of the KABI whitelist archive."""
    kabi_tarname_options = [
        "kernel-abi-stablelists-{}.tar.bz2".format(version[:-4]),
        "kernel-abi-whitelists-{}.tar.bz2".format(version[:-4]),
        "kernel-abi-whitelists.tar.bz2"
    ]
    if "-" in version:
        kabi_tarname_options.append(
            "kernel-abi-whitelists-{}.tar.bz2".format(
                version.split("-")[1].split(".")[0]))
        kabi_tarname_options.append(
            "kernel-abi-stablelists-{}.tar.bz2".format(
                version.split("-")[1].split(".")[0]))
    for kabi_tarname in kabi_tarname_options:
        if os.path.isfile(kabi_tarname):
            cwd = os.getcwd()
            # Create temp dir and extract the files there
            os.mkdir("kabi")
            os.rename(kabi_tarname, "kabi/{}".format(kabi_tarname))
            os.chdir("kabi")
            check_call(["tar", "-xjf", kabi_tarname])

            # Copy the desired whitelist
            kabi_dir = "kabi-current"
            if not os.path.isdir(kabi_dir):
                # kabi-current directory does not exist, extract the current
                # RHEL version from kernel.spec
                os.chdir(cwd)
                with open("kernel.spec", "r") as kernel_spec:
                    for line in kernel_spec:
                        if line.startswith("KABI_CURRENT="):
                            kabi_dir = line[len("KABI_CURRENT="):].strip()
                            break
                os.chdir("kabi")

            for filename in kabi_filenames:
                file = os.path.join(kabi_dir, filename)
                if (os.path.isfile(file)):
                    kabi_file = os.path.join(cwd, filename)
                    shutil.copyfile(file, kabi_file)
                    break

            os.chdir(cwd)
            # Clean temp dir
            shutil.rmtree("kabi")
            return kabi_file
    return None


def get_kernel_tar_from_upstream(version):
    """
    Download sources of the required kernel version from the upstream
    (www.kernel.org). Sources are stored as .tar.xz file.
    :returns Name of the tar file containing the sources.
    """
    url = "https://www.kernel.org/pub/linux/kernel/"

    # Version directory (different naming style for versions under and
    # over 3.0)
    if StrictVersion(version) < StrictVersion("3.0"):
        url += "v{}/".format(version[:3])
    else:
        url += "v{}.x/".format(version[:1])

    tarname = "linux-{}.tar.xz".format(version)
    url += tarname

    # Download the tarball with kernel sources
    print("Downloading kernel version {}".format(version))
    urlretrieve(url, tarname, show_progress)

    return tarname


def get_kernel_from_srpm(version, rpmname, url):
    """
    Download a source RPM with the kernel and extract it.
    :return Name of the tar file containing the kernel sources.
    """
    # Download the source RPM package
    print("Downloading kernel version {}".format(version))
    urlretrieve(url, rpmname, show_progress)

    # Extract files from SRPM package
    with open(os.devnull, "w") as devnull:
        rpm_cpio = Popen(["rpm2cpio", rpmname], stdout=PIPE,
                         stderr=devnull)
        check_call(["cpio", "-idmv"], stdin=rpm_cpio.stdout,
                   stderr=devnull)

    tarname = "linux-{}.tar.xz".format(version)
    if not os.path.isfile(tarname):
        tarname = "linux-{}.tar.bz2".format(version)
    return tarname


def get_kernel_tar_from_brew(version):
    """
    Download sources of the required RHEL kernel from Brew.
    Sources are part of the SRPM package and need to be extracted out of it.
    :returns Name of the tar file containing the sources.
    """
    url = "http://download.eng.bos.redhat.com/brewroot/packages/kernel/"
    ver, release = version.split("-")
    url += "{}/{}/src/".format(ver, release)
    rpmname = "kernel-{}.src.rpm".format(version)
    url += rpmname
    return get_kernel_from_srpm(version, rpmname, url)


centos_kernel_map = {
    "3.10.0-123.el7": "7.0.1406",
    "3.10.0-229.el7": "7.1.1503",
    "3.10.0-327.el7": "7.2.1511",
    "3.10.0-514.el7": "7.3.1611",
    "3.10.0-693.el7": "7.4.1708",
    "3.10.0-862.el7": "7.5.1804",
    "3.10.0-957.el7": "7.6.1810",
    "3.10.0-1062.el7": "7.7.1908",
    "3.10.0-1127.el7": "7.8.2003",
    "4.18.0-80.el8": "8.0.1905",
    "4.18.0-147.el8": "8.1.1911",
    "4.18.0-193.el8": "8.2.2004",
    "4.18.0-240.el8": "8.3.2011",
    "4.18.0-305.el8": "8.4.2105",
    "4.18.0-348.el8": "8.5.2111"
}


def get_kernel_tar_from_centos(version):
    """
    Download sources of the required kernel from the CentOS file server.
    The correct address is determined using the centos_kernel_map.
    Sources are part of the SRPM package and need to be extracted out of it.
    :returns Name of the tar file containing the sources.
    """
    url = "http://vault.centos.org/"
    url += centos_kernel_map[version]
    url += "/BaseOS" if version.endswith(".el8") else "/os"
    url += "/Source/SPackages/"
    rpmname = "kernel-{}.src.rpm".format(version)
    url += rpmname
    return get_kernel_from_srpm(version, rpmname, url)


def extract_tar(tarname):
    """Extract kernel sources from .tar.xz file."""
    print("Extracting")
    if tarname.endswith(".tar.xz"):
        tar_opts = "-xJf"
        dirname = tarname[:-7]
    else:
        # Filename ends with .tar.bz2
        tar_opts = "-xjf"
        dirname = tarname[:-8]
    check_call(["tar", tar_opts, tarname])
    os.remove(tarname)
    print("Done")
    return os.path.abspath(dirname)


def get_kernel_source(version):
    """Download the sources of the required kernel version."""
    # Deduce source where kernel will be downloaded from.
    # The choice is done based on version string, if it has the release part
    # (e.g. 3.10.0-655.el7) it must be downloaded from Brew (StrictVersion will
    # raise exception on such version string). If Brew is unavailable,
    # download from CentOS.
    try:
        StrictVersion(version)
        tarname = get_kernel_tar_from_upstream(version)
    except ValueError:
        try:
            gethostbyname("download.eng.bos.redhat.com")
            tarname = get_kernel_tar_from_brew(version)
        except socket_error:
            tarname = get_kernel_tar_from_centos(version)

    kernel_dir = extract_tar(tarname)
    print("Kernel sources for version {} are in directory {}".format(
        version, kernel_dir))
    return kernel_dir


def symlink_gcc_header():
    """
    Symlink include/linux/compiler-gccX.h for the current GCC version with
    the most recent header in the downloaded kernel.
    This is useful when the system GCC is newer than the one supported for
    kernel building.
    :param major_version: Major version of GCC to be used for compilation
    """
    major_version = check_output(["gcc", "-dumpversion"]).decode("utf-8")[0]
    include_path = os.path.abspath("include/linux")
    dest_file = os.path.join(include_path,
                             "compiler-gcc{}.h".format(major_version))
    if not os.path.isfile(dest_file):
        # Search for the most recent version of header provided in the
        # analysed kernel and symlink the current version to it
        regex = re.compile(r"^compiler-gcc(\d+)\.h$")
        max_major = 0
        for file in os.listdir(include_path):
            match = regex.match(file)
            if match and int(match.group(1)) > max_major:
                max_major = int(match.group(1))

        if max_major > 0:
            src_file = os.path.join(include_path,
                                    "compiler-gcc{}.h".format(max_major))
            os.symlink(src_file, dest_file)


def configure_kernel():
    """
    Configure kernel.
    For kernels downloaded from Brew, use the provided config file.
    For kernels downloaded from upstream, configure all as module (run
    `make allmodconfig`).
    Then run:
        make prepare
        make modules_prepare
    """
    print("Configuring and preparing modules")
    if not os.path.isfile(".config"):
        call_and_print(["make", "allmodconfig"])
    else:
        call_and_print(["make", "olddefconfig"])
    call_and_print(["scripts/config", "--disable", "CONFIG_RETPOLINE"])
    call_and_print(["make", "prepare",
                    "EXTRA_CFLAGS=" + EXTRA_CFLAGS, "CFLAGS=" + CFLAGS,
                    "HOSTLDFLAGS=" + LDFLAGS])
    call_and_print(["make", "modules_prepare",
                    "EXTRA_CFLAGS=" + EXTRA_CFLAGS, "CFLAGS=" + CFLAGS,
                    "HOSTLDFLAGS=" + LDFLAGS])


def autogen_time_headers():
    """
    Generate headers for kernel/time module (if the module exists) that
    need to be generated automatically.
    """
    try:
        with open(os.devnull, 'w') as null:
            check_call(["make", "-s", "kernel/time.o",
                        "EXTRA_CFLAGS=" + EXTRA_CFLAGS, "CFLAGS=" + CFLAGS],
                       stdout=null, stderr=null)
    except CalledProcessError:
        pass


# Parse CLI arguments
ap = ArgumentParser(description="Get RHEL-based and upstream Linux kernel "
                                "source")
ap.add_argument("version")
ap.add_argument("--output-dir", "-o", help="output directory")
ap.add_argument("--kabi", help="include the KABI whitelist",
                action="store_true")
args = ap.parse_args()

# Create the output directory
if not args.output_dir:
    output_dir = os.getcwd()
else:
    output_dir = os.path.abspath(args.output_dir)
if not os.path.isdir(output_dir):
    os.mkdir(output_dir)

cwd = os.getcwd()
tmp = mkdtemp()
os.chdir(tmp)

# Download source
kernel_dir = get_kernel_source(args.version)

# Configure
config_file = get_config_file(args.version)
if config_file:
    os.rename(config_file, os.path.join(kernel_dir, ".config"))
os.chdir(kernel_dir)
symlink_gcc_header()
configure_kernel()
autogen_time_headers()
os.chdir(tmp)

# Extract KABI list
if args.kabi:
    kabi_filenames = ["kabi_whitelist_x86_64", "kabi_stablelist_x86_64"]
    kabi_file = get_kabi_file(args.version, kabi_filenames)
    if kabi_file:
        os.rename(kabi_file, os.path.join(kernel_dir,
                                          os.path.basename(kabi_file)))

target = os.path.join(output_dir, os.path.basename(kernel_dir))
if os.path.isdir(target):
    shutil.rmtree(target)
shutil.move(kernel_dir, target)
shutil.rmtree(tmp)
os.chdir(cwd)
