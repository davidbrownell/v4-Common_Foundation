The contents of this directory are convoluted, as all outputs after code generation must reside in the same directory (GitHub doesn't allow nested directories). To make things less confusing, the following naming convention is used for files in the directory:

`callable_`: Callable workflows that can be invoked by other repositories in the implementation of their own validation processes.

`event_`: Workflows that are triggered by an event (pr, push, periodic, etc.).

`manual_`: Workflows that can be triggered by a human on github. These workflows should invoke functionality similar to workflows invoked by events.

`sca_`: Static Code Analysis (SCA) workflows triggered by PRs, commits to mainline branches, and periodic invocations.

`validate_`: Workflows that validate the current repository and can be invoked by other repositories (generally, as part of their dependency-validation process).
