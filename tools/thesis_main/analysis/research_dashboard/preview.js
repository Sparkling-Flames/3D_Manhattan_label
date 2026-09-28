/* Studio remains unchanged; make unavailable WebGL/resources explicit in the embedded case. */
'use strict';
function previewUnavailable(event) {
  const note=document.getElementById('fatal');
  if(note){note.hidden=false;note.textContent='3D 预览不可用：浏览器图形支持或本地资源加载失败。可返回案例查看原图和坐标表。';}
}
window.addEventListener('error',previewUnavailable);
window.addEventListener('unhandledrejection',previewUnavailable);
