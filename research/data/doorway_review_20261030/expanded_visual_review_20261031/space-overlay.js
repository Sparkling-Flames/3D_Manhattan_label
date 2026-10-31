// Reuse the existing original-annotation renderer; space projections are opt-in.
for (const [i, section] of [...document.querySelector('main').children].entries()) {
  const r=reviewItems[i], svgs=section.querySelectorAll('svg'), panorama=svgs[0], bev=svgs[1];
  const cuts=svgEl('g',{'aria-label':'已划分空间底面边界'},panorama);
  cuts.style.display='none';
  const extent=Math.max(...r.spaces.flat().map(p=>Math.max(Math.abs(p[0]),Math.abs(p[1]))));
  r.spaces.forEach((poly,j)=>{
    const color=j?'#f78b20':'#00a9bc';
    for(let k=0;k<poly.length;k++) {
      const a=poly[k],b=poly[(k+1)%poly.length];
      edge([a[0],-1,a[1]],[b[0],-1,b[1]],cuts,color);
    }
    const xs=poly.map(p=>p[0]),ys=poly.map(p=>p[1]);
    svgEl('text',{x:(Math.min(...xs)+Math.max(...xs))/2,y:(Math.min(...ys)+Math.max(...ys))/2,
      'font-size':extent*.07,'text-anchor':'middle',fill:j?'#99500b':'#006c78',
      'paint-order':'stroke',stroke:'white','stroke-width':extent*.012},bev).textContent=`空间${j+1}`;
  });
  svgEl('text',{x:extent*.025,y:-extent*.025,'font-size':extent*.055,fill:'#a00000'},bev).textContent='相机';
  const toggle=text('button','显示／隐藏原图上的空间切分',section);
  toggle.setAttribute('aria-pressed','false');
  toggle.onclick=()=>{const show=cuts.style.display==='none';cuts.style.display=show?'':'none';toggle.setAttribute('aria-pressed',String(show));};
}
