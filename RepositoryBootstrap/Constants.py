# ----------------------------------------------------------------------
# |
# |  Constants.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-08 13:33:35
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains Constants used during the Repository bootstrapping process"""

import textwrap


# ----------------------------------------------------------------------
SETUP_ENVIRONMENT_NAME                                  = "Setup"
SETUP_ENVIRONMENT_CUSTOMIZATION_FILENAME                = "{}_custom.py".format(SETUP_ENVIRONMENT_NAME)

ACTIVATE_ENVIRONMENT_NAME                               = "Activate"
ACTIVATE_ENVIRONMENT_CUSTOMIZATION_FILENAME             = "{}_custom.py".format(ACTIVATE_ENVIRONMENT_NAME)

DEACTIVATE_ENVIRONMENT_NAME                             = "Deactivate"

DEFAULT_ENVIRONMENT_NAME                                = "DefaultEnv"
DEFAULT_CONFIGURATION_NAME                              = "DefaultConfig"

HOOK_ENVIRONMENT_CUSTOMIZATION_FILENAME                 = "ScmHook_custom.py"

TEMPORARY_FILE_EXTENSION                                                    = ".SourceRepositoryTools"
GENERATED_DIRECTORY_NAME                                                    = "Generated"
GENERATED_BOOTSTRAP_JSON_FILENAME                                           = "EnvironmentBootstrap.json"
GENERATED_BOOTSTRAP_DATA_FILENAME                                           = "EnvironmentBootstrap.data"
GENERATED_ACTIVATION_FILENAME                                               = "EnvironmentActivation.json"
GENERATED_ACTIVATION_ORIGINAL_ENVIRONMENT_FILENAME_TEMPLATE                 = "EnvironmentActivation.OriginalEnvironment.{{}}{}".format(TEMPORARY_FILE_EXTENSION)

LIBRARIES_SUBDIR                                        = "Libraries"
SCRIPTS_SUBDIR                                          = "Scripts"
TOOLS_SUBDIR                                            = "Tools"

AGNOSTIC_OS_NAME                                        = "Agnostic"
SRC_OS_NAME                                             = "src"
CUSTOMIZATIONS_OS_NAME                                  = "customizations"

# Sometimes, we don't want code within a directory ever be discovered during the repository discovery
# process (for example, code used to run a CI process should not be discovered by workers exercising
# a specific branch).
#
# Create a file with the name below to prevent a directory and its descendants from being discovered.
IGNORE_DIRECTORY_AS_BOOTSTRAP_DEPENDENCY_SENTINEL_FILENAME  = "IgnoreAsBootstrapDependency"
IGNORE_DIRECTORY_AS_TOOL_SENTINEL_FILENAME                  = "IgnoreAsTool"

# Directories may use any of these prefixes when separating version-specific content
POTENTIAL_VERSION_PREFIXES                  = ["v", "V", "r", "R"]

# ----------------------------------------------------------------------
# |  Custom Methods defined in `SETUP_ENVIRONMENT_CUSTOMIZATION_FILENAME`

# Callable[
#     [
#         <See `EncounteredRepoData.Create` in ./Impl/RepositoryMapCalculator.py for a list of arguments>
#     ],
#     Union[
#         Configuration.Configuration,
#         Dict[Optional[str], Configuration.Configuration],
#     ],
# ]
SETUP_ENVIRONMENT_CONFIGURATIONS_METHOD_NAME            = "GetConfigurations"

# Callable[
#     [
#         <See `_SetupCustom` in ./Impl/Setup.py for a list of arguments>
#     ],
#     List[Common_Foundation.Shell.Commands.Command],
# ]
SETUP_ENVIRONMENT_ACTIONS_METHOD_NAME                   = "GetCustomActions"

# ----------------------------------------------------------------------
# |  Custom Methods defined in `ACTIVATE_ENVIRONMENT_CUSTOMIZATION_FILENAME`

# Callable[
#     [
#         <See `_ActivateCustom` in ./Impl/Activate.py for a list of arguments>
#     ],
#     List[Common_Foundation.Shell.Commands.Command],
# ]
ACTIVATE_ENVIRONMENT_ACTIONS_METHOD_NAME                                    = "GetCustomActions"

# Callable[
#     [
#         <See `_ActivateCustom` in ./Impl/Activate.py for a list of arguments>
#     ],
#     List[Common_Foundation.Shell.Commands.Command],
# ]
ACTIVATE_ENVIRONMENT_ACTIONS_EPILOGUE_METHOD_NAME                           = "GetCustomActionsEpilogue"

# Callable[
#     [
#         <See `_CreateCommandsImpl` in ./Impl/ActivateActivities/ScriptsActivateActivity.py for a list of arguments>
#     ],
#     Union[
#         Tuple[
#             Impl.ActivateActivities.ScriptActivateActivity.ExtractorMap,
#             List[Impl.ActivateActivities.ScriptActivateActivity.DirGenerator],
#         ],
#         Tuple[
#             Impl.ActivateActivities.ScriptActivateActivity.ExtractorMap,
#             Impl.ActivateActivities.ScriptActivateActivity.DirGenerator,
#         ],
#         Impl.ActivateActivities.ScriptActivateActivity.ExtractorMap,
#     ],
# ]
ACTIVATE_ENVIRONMENT_CUSTOM_SCRIPT_EXTRACTOR_METHOD_NAME                    = "GetCustomScriptExtractors"

# ----------------------------------------------------------------------
SCRIPT_LIST_NAME                                                            = "DevEnvScripts"

# ----------------------------------------------------------------------
# |  Custom Methods defined in `HOOK_ENVIRONMENT_CUSTOMIZATION_FILENAME`
HOOK_ENVIRONMENT_COMMIT_METHOD_NAME                     = "OnCommitting"
HOOK_ENVIRONMENT_PUSH_METHOD_NAME                       = "OnPushing"
HOOK_ENVIRONMENT_PULL_METHOD_NAME                       = "OnPulled"

# ----------------------------------------------------------------------
REPOSITORY_ID_FILENAME                                  = "__RepositoryId__"

REPOSITORY_ID_CONTENT_TEMPLATE                          = textwrap.dedent(
    """\
    This file is used to uniquely identify this repository for the purposes of dependency management.
    Other repositories that depend on this one will search for this file upon initial setup and
    generate information that is used when activating development environments.

    **** PLEASE DO NOT MODIFY, REMOVE, OR RENAME THIS FILE, AS DOING SO WILL LIKELY BREAK OTHER REPOSITORIES! ****

    Friendly Name:      {name}
    Id:                 {id}

    Version 4.0.0
    """)

# ----------------------------------------------------------------------
# |  Environment Variable Names
DE_ENVIRONMENT_NAME                                     = "DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME"

DE_FOUNDATION_ROOT_NAME                                 = "DEVELOPMENT_ENVIRONMENT_FOUNDATION"

DE_REPO_ROOT_NAME                                       = "DEVELOPMENT_ENVIRONMENT_REPOSITORY"
DE_REPO_CONFIGURATION_NAME                              = "DEVELOPMENT_ENVIRONMENT_REPOSITORY_CONFIGURATION"
DE_REPO_GENERATED_NAME                                  = "DEVELOPMENT_ENVIRONMENT_REPOSITORY_GENERATED"
DE_OPERATING_SYSTEM_NAME                                = "DEVELOPMENT_ENVIRONMENT_OPERATING_SYSTEM"

DE_ORIGINAL_PATH                                        = "DEVELOPMENT_ENVIRONMENT_ORIGINAL_PATH"

DE_REPO_ACTIVATED_KEY                                   = "DEVELOPMENT_ENVIRONMENT_REPOSITORY_ACTIVATED_KEY"

DE_SHELL_NAME                                           = "DEVELOPMENT_ENVIRONMENT_SHELL_NAME"
