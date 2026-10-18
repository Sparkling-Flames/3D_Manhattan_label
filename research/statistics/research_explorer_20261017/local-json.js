/* Local script files allow file:// viewing without an HTTP server. */
'use strict';
window.researchLocalData = Object.create(null);
window.readResearchJSON = async function (path) {
  if (location.protocol !== 'file:') {
    const response = await fetch(path, {cache: 'no-cache'});
    if (!response.ok) throw Error(`${response.status} · ${path}`);
    return response.json();
  }
  const url = new URL(path, location.href).href;
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = url.replace(/\.json$/, '.js');
    const cleanup = () => { delete window.researchLocalData[url]; script.remove(); };
    script.onload = () => {
      const data = window.researchLocalData[url];
      cleanup();
      if (data === undefined) reject(Error('本地数据未注册：' + path));
      else resolve(data);
    };
    script.onerror = () => { cleanup(); reject(Error('本地数据缺失，请重新生成离线数据：' + path)); };
    document.head.appendChild(script);
  });
};
