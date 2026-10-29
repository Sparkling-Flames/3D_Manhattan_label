'use strict';
document.querySelectorAll('[data-version-switch]').forEach(select=>{
 select.addEventListener('change',()=>{if(select.value==='v2')location.href='index.html#release=v2&module='+encodeURIComponent(select.dataset.v2Module||'overview');});
});
