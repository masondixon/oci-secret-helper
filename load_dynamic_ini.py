"""Backward-compatible import path for OCI Secret Helper."""

from oci_secret_helper.dynamic_ini import *  # noqa: F401,F403
from oci_secret_helper.dynamic_ini import main


if __name__ == "__main__":
    main()
