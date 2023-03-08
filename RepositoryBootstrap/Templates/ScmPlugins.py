# pylint: disable=invalid-name, missing-module-docstring

from RepositoryBootstrap.DataTypes import SCMPlugin  # type: ignore  # pylint: disable=import-error


# ----------------------------------------------------------------------
def GetPlugins() -> list[SCMPlugin]:
    raise Exception("Implement me")
