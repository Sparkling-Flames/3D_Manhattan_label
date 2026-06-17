# Stage 1 Private Setup Note

Please do not share this note, the Label Studio link, or the logging token with anyone else.

## 1. Label Studio Website

Use the following Label Studio website:

https://label.sparkle0825.top

Please use Chrome or Edge on a desktop or laptop computer.

Do not use incognito/private mode.

## 2. Logging Token Setup

The logging token is used to record active annotation time.

Open the browser console on the Label Studio website and run the setup command provided by the researcher.

Logging Token:

```javascript
localStorage.setItem("HOHONET_LOG_TOKEN", "hoho-20260228-zjw200408250904!");

localStorage.setItem(
  "HOHONET_HELPER_BASE_URL",
  "https://label.sparkle0825.top",
);
```

After setting the token, refresh the page.

## 3. Important Rules

- Use only your assigned Label Studio tasks.
- Complete annotations according to the project instructions and annotation rules.
- Before starting each annotation session, check that log time recording is working normally. In most cases, logging stops only if browser cache/storage has been cleared and the token needs to be set again.
- Do not share the Label Studio website, token, or project materials with anyone else.
- Do not modify or remove the logging setup during annotation.
- Contact the researcher through Upwork if you encounter technical issues or access problems.
