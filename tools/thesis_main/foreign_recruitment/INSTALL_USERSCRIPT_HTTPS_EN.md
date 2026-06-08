# Install The HTTPS Helper Script

## 1. Install A Userscript Manager

Use Chrome or Edge on a desktop/laptop.

Install one of these browser extensions:

- Tampermonkey
- Violentmonkey

Do not use incognito/private browsing mode.

## 2. Install The Helper Script

Install:

```text
ls_userscript_annotator_https_en.user.js
```

The script should show this name:

```text
HoHoNet Helper Official Annotator HTTPS EN
```

For troubleshooting only, the researcher may ask you to install:

```text
ls_userscript_annotator_https_en_debug.user.js
```

Do not enable the normal English helper and the debug English helper at the same
time. Enable only one HoHoNet helper script in your userscript manager.

It should only run on:

```text
https://label.sparkle0825.top/*
```

## 3. Open Your Assigned Link

Use the link provided by the researcher. It should look similar to:

```text
https://label.sparkle0825.top/?participantId=YOUR_CONNECT_ID
```

If the link starts with `http://`, do not use it. Ask the researcher for the
HTTPS link.

## 4. Set The Logging Token

The logging token is not passed in the URL. Label Studio navigation can remove
URL query parameters after a worker enters a project, so the token must be set
once in the browser.

Open `https://label.sparkle0825.top/`, then open the browser console and run:

```javascript
localStorage.setItem("HOHONET_LOG_TOKEN", "hoho-20260228-zjw200408250904!");

localStorage.setItem("HOHONET_HELPER_BASE_URL", "https://label.sparkle0825.top");
```

Then refresh the Label Studio page.

Researcher note: the `HOHONET_LOG_TOKEN` value above must be exactly the same as
the server-side `HOHONET_LOG_TOKEN` used by the `/log_time` service. If the HTTPS
entry point proxies to the same active-time log server as the Chinese annotator
setup, use the same token as the Chinese setup.

Do not publish the token in public recruitment text. Send it only to accepted
participants through a private instruction message.

## 5. Check Active-Time Logging

Before each annotation session:

1. Open the assigned Label Studio project.
2. Open one assigned task.
3. Move the mouse or interact with the task for a few seconds.
4. Open the browser developer tools if the researcher asks you to check logging.
5. In the Network tab, confirm that `/log_time` appears and returns a successful
   status such as `200` or `204`, or ask the researcher to confirm the server log.

If logging fails, stop before doing real annotation.

## 6. Troubleshooting

If the browser console shows `403 Forbidden` for `/log_time`, the logging token
is missing or wrong. Set `HOHONET_LOG_TOKEN` in browser localStorage again, then
refresh the Label Studio page.

If the browser console shows `Missing HOHONET_LOG_TOKEN`, do not continue real
annotation until the localStorage token has been set.

If the token is already set but `/log_time` still reports `token= (len=0)`,
check that only one HoHoNet helper script is enabled in the userscript manager.
Disable old HTTP, Chinese, debug, or previous English helper scripts for this
browser profile. Then refresh the Label Studio page and run:

```javascript
console.log(window.__HOHONET_HELPER_SCRIPT_VERSION__);
console.log(window.__HOHONET_HELPER_SCRIPT_FLAVOR__);
console.log((localStorage.getItem("HOHONET_LOG_TOKEN") || "").length);
console.log(localStorage.getItem("HOHONET_HELPER_BASE_URL"));
```

The expected script flavor is:

```text
foreign_https_en
```

If you are intentionally using the debug helper, the expected script flavor is:

```text
foreign_https_en_debug
```

If the 3D viewer does not load, refresh the task page once.

If the helper panel does not appear, check that the userscript extension is
enabled and that you are using the HTTPS domain.

If you accidentally opened an unrelated task or project, tell the researcher.
Do not continue annotating unrelated tasks.
