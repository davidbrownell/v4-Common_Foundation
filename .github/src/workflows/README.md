The contents of this directory are convoluted, as all outputs after code generation must reside in the same directory (GitHub doesn't allow nested directories). To make things less confusing, the following naming convention is used for files in the directory:

`event_`: Workflows that are triggered by an event (pr, push, periodic, etc.).

`exercise_`: Workflow(s) to validate this repository; these workflows may be invoked by other repositories as a part of their dependency validation process.

`impl_`: Callable workflows that implement functionality used by other workflows in this repository. These workflows cannot be invoked outside of this repository.

`manual_`: Workflows that can be triggered by a human on github. These workflows should invoke functionality similar to workflows invoked by events.
