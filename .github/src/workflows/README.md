The contents of this directory are convoluted, as the file outputs after code generation must reside in the same directory (GitHub doesn't allow nested directories). Therefore, the following naming convention is used for files in the directory:

`callable_`: Generic callable workflows that can be invoked by workflows in other repositories.

`exercise_`: Workflows that exercises the functionality in this repository and callable by workflows in other repositories (as a part of `main` -> `release` branch validation).

`on_`: Workflows responding to events on this repository.
