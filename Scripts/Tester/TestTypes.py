# ----------------------------------------------------------------------
# |
# |  TestTypes.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-12 15:03:45
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains properties for well-known test types"""

from dataclasses import dataclass, field
from enum import auto, Enum
from typing import List, Optional


# ----------------------------------------------------------------------
class DeploymentType(Enum):
    """Indicates how a test must be deployed before it can be used"""

    Local                                   = auto()    # Can be run on a developer's machine
    ProductionLike                          = auto()    # Must be run on a system similar to production
    Production                              = auto()    # Must be run on a production deployment


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class TestTypeInfo(object):
    """Information about specific types of tests"""

    name: str

    deployment_type: Optional[DeploymentType]

    code_coverage: bool                     = field(kw_only=True)
    execute_in_parallel: bool               = field(kw_only=True)

    description: str


# ----------------------------------------------------------------------
TYPES: List[TestTypeInfo]                   = [
    TestTypeInfo("UnitTests",              code_coverage=True,  execute_in_parallel=True,  deployment_type=None,                          description="Tests that exercise a single function or method."),
    TestTypeInfo("FunctionalTests",        code_coverage=True,  execute_in_parallel=True,  deployment_type=None,                          description="Tests that exercise multiple functions or methods."),
    TestTypeInfo("IntegrationTests",       code_coverage=False, execute_in_parallel=True,  deployment_type=DeploymentType.Local,          description="Tests that exercise 1-2 components with local setup requirements."),
    TestTypeInfo("SystemTests",            code_coverage=False, execute_in_parallel=False, deployment_type=DeploymentType.ProductionLike, description="Tests that exercise 1-2 components with production-like setup requirements."),
    TestTypeInfo("LocalEndToEndTests",     code_coverage=False, execute_in_parallel=False, deployment_type=DeploymentType.Local,          description="Tests that exercise 2+ components with local setup requirements."),
    TestTypeInfo("EndToEndTests",          code_coverage=False, execute_in_parallel=True,  deployment_type=DeploymentType.Production,     description="Tests that exercise 2+ components with production setup requirements."),
    TestTypeInfo("BuildVerificationTests", code_coverage=False, execute_in_parallel=False, deployment_type=DeploymentType.Production,     description="Tests intended to determine at a high level if a build/deployment is working as expected."),
    TestTypeInfo("PerformanceTests",       code_coverage=False, execute_in_parallel=False, deployment_type=DeploymentType.Production,     description="Tests measuring performance across a variety of dimensions."),
]
