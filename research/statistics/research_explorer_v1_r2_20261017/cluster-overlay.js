/* Same-cluster overlays, following the historical studio's colored member toggles. */
window.ClusterOverlay=(()=>{
const colors=['#00d4ff','#ff5470','#ffdf38','#70ef68','#d59bff','#ff9b37','#ffffff','#f85de3'];
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function marks(points,color){return points.map(([x,y],i)=>`<circle cx="${x}" cy="${y}" r="3.2" fill="${color}" stroke="#172331" stroke-width="1"><title>原点 ${i}</title></circle>`).join('');}
function mount(host,image,layers){
 host.innerHTML=`<div class="stack-tools"><button data-full>放大／全屏</button><label>点透明度 <input data-alpha type="range" min=".1" max="1" step=".1" value=".8"></label><label>底图亮度 <input data-bg type="range" min=".1" max="1" step=".1" value=".6"></label></div><svg class="stack-svg" viewBox="0 0 1024 512" role="img" aria-label="${esc(image.image_code)} 多份原标注叠加"><image href="${esc(image.photo)}" width="1024" height="512" opacity=".6"/>${layers.map((l,k)=>`<g data-layer="${k}" opacity=".8">${l.members.map(i=>marks(image.records[i].points,colors[k%colors.length])).join('')}</g>`).join('')}</svg><div class="stack-legend">${layers.map((l,k)=>`<label style="border-left:5px solid ${colors[k%colors.length]}"><input type="checkbox" data-toggle="${k}" checked>${esc(l.label)}</label>`).join('')}</div>`;
 const svg=host.querySelector('svg');
 host.querySelector('[data-alpha]').oninput=e=>svg.querySelectorAll('g').forEach(g=>g.setAttribute('opacity',e.target.value));
 host.querySelector('[data-bg]').oninput=e=>svg.querySelector('image').setAttribute('opacity',e.target.value);
 host.querySelectorAll('[data-toggle]').forEach(c=>{c.onchange=()=>svg.querySelector(`[data-layer="${c.dataset.toggle}"]`).style.display=c.checked?'':'none';});
 host.querySelector('[data-full]').onclick=()=>{if(document.fullscreenElement)document.exitFullscreen();else host.requestFullscreen();};
}
return {mount,marks};
})();
