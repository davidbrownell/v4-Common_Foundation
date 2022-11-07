## Why is this so Complicated?

At the time this code was written, GitHub supports the following techniques for workflow composition:

  - Callable workflows
  - Composite actions

Unfortunately, Callable workflows are not customizable (in that it isn't possible to add new steps) and therefore need to be either duplicated to invoke new steps or a separate workflow must be created to support the new steps. Unfortunately, a separate workflow means a different runner, different code sync, etc.

I expect that GitHub will eventually support this functionality natively, but for now we are using `Jinja2CodeGenerator` in the support of more fine-grained workflow composition.
