# Bluesky Web Plotting

A Dash + plotly bluesky plotting sevice/callback.

This fork of the original repo is designed to experiment with a timeline interface, a la Final Cut Pro X. This is documented in the design documents. 

The first design document is in [design_documentation/CONFIG_SPEC.md] and describes the behaviour and configruation structure of the timeline. 




<img width="1675" height="1265" alt="local_window" src="https://github.com/user-attachments/assets/15bdb2d5-666c-4024-8105-b90d77df9bcc" />

## Running examples

All the tests also function as examples.

1. Install `[dev][local]` dependencies and
2. `$ export BLUESKY_WEB_PLOTS_EXAMPLE_MODE=1`
3. Run `pytest`. Each test will remain running (so you can look around) until the generated local window is closed.
4. You can also access the same plots from the browser (default [https://localhost:12354](https://localhost:12354)).

