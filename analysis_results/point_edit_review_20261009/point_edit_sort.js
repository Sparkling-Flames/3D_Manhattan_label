/* Adapter only. Pointer drag implementation below is copied verbatim from order_studio_20260926.js. */
window.LegacyPairSort=function(options){
 const dragArea=options.container;let previewOrder=[],pointerDrag=null,hoveredPair=null,geometry=null,demoOrder=[];
 const activeSource=()=>({role:'annotation'}),drawPanorama=options.redraw;
 const select=item=>options.onSelect(item.index);
 const setPreviewOrder=(order,action)=>{if(options.isEditable())options.onOrder(order,action);};
 function drawDrag(){
  const pairs=options.getPairs();dragArea.replaceChildren();
  for(let i=0;i<previewOrder.length;i++){
   const b=document.createElement('button'),pair=pairs[previewOrder[i]];b.className='pair-token';b.dataset.position=i;b.dataset.pair=pair.join('|');
   const number=document.createElement('span');number.className='sequence-circle';number.textContent=i+1;
   const names=document.createElement('span');names.textContent=options.label(pair[0])+' / '+options.label(pair[1]);b.append(number,names);
   b.title='角点位置 '+(i+1)+'：上 '+options.label(pair[0])+' / 下 '+options.label(pair[1])+'；整组拖动，原点号不变';
   b.disabled=!options.isEditable();b.onpointerdown=e=>startPairDrag(e,b,i);
   b.onmouseenter=b.onfocus=()=>{hoveredPair=previewOrder[i];drawPanorama();};b.onmouseleave=b.onblur=()=>{hoveredPair=null;drawPanorama();};
   b.onclick=e=>{if(e.detail===0&&geometry)select({kind:'point',index:i,endpoint:'top'});};
   b.onkeydown=e=>{if(e.altKey&&['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();movePair(i,e.key==='ArrowLeft'?Math.max(0,i-1):Math.min(previewOrder.length,i+2));}};
   dragArea.append(b);
  }
 }
 function startPairDrag(e,button,index){
 if(e.button!==0||pointerDrag)return;
 e.preventDefault();button.focus();
 pointerDrag={id:e.pointerId,button,index,x:e.clientX,y:e.clientY,lifted:false};
 dragArea.setPointerCapture(e.pointerId);
}
dragArea.onpointermove=e=>{
 const d=pointerDrag;if(!d||e.pointerId!==d.id)return;
 if(!d.lifted&&Math.hypot(e.clientX-d.x,e.clientY-d.y)<5)return;
 if(!d.lifted){
  const rect=d.button.getBoundingClientRect();d.lifted=true;d.dx=d.x-rect.left;d.dy=d.y-rect.top;
  d.ghost=d.button.cloneNode(true);d.ghost.classList.add('pair-floating');d.ghost.style.width=rect.width+'px';document.body.append(d.ghost);
  d.button.remove();d.marker=document.createElement('span');d.marker.className='pair-insertion';d.marker.setAttribute('aria-hidden','true');
 }
 d.ghost.style.left=(e.clientX-d.dx)+'px';d.ghost.style.top=(e.clientY-d.dy)+'px';
 // Keep the gap marker out of layout so the remaining cards close up immediately.
 const cards=[...dragArea.querySelectorAll('.pair-token')],areaBox=dragArea.getBoundingClientRect();
 const rects=cards.map(b=>({left:areaBox.left+b.offsetLeft,top:areaBox.top+b.offsetTop,width:b.offsetWidth,height:b.offsetHeight,right:areaBox.left+b.offsetLeft+b.offsetWidth}));
 let nearest=0,best=Infinity;
 rects.forEach((r,i)=>{const dy=Math.abs(e.clientY-(r.top+r.height/2));if(dy<best){best=dy;nearest=i;}});
 const row=rects.map((r,i)=>({r,i})).filter(({r})=>Math.abs(r.top-rects[nearest]?.top)<5);
 const next=row.find(({r})=>e.clientX<r.left+r.width/2);
 d.target=next?next.i:row.length?row[row.length-1].i+1:0;
 const last=rects.at(-1),gap=12;
 const tail=last&&(last.right+gap+last.width<=areaBox.right-9
  ?{...last,left:last.right+gap}:{...last,left:rects[0].left,top:last.top+last.height+gap});
 const slots=[...rects,tail];
 cards.forEach((b,i)=>{const r=rects[i],slot=slots[i+(i>=d.target?1:0)];b.style.transform=`translate(${slot.left-r.left}px,${slot.top-r.top}px)`;});
 const anchor=slots[d.target];
 if(anchor){d.marker.style.left=(anchor.left-areaBox.left)+'px';d.marker.style.top=(anchor.top-areaBox.top)+'px';d.marker.style.width=anchor.width+'px';d.marker.style.height=anchor.height+'px';dragArea.append(d.marker);}
};
function finishPairDrag(cancel=false){
 const d=pointerDrag;if(!d)return;pointerDrag=null;
 if(dragArea.hasPointerCapture(d.id))dragArea.releasePointerCapture(d.id);
 if(d.lifted){
  d.ghost.remove();d.marker.remove();
  if(!cancel){const empty=activeSource()?.role==='empty',order=[...(empty?demoOrder:previewOrder)];const [pair]=order.splice(d.index,1);order.splice(d.target??d.index,0,pair);
   if(empty){demoOrder=order;drawDrag();}else setPreviewOrder(order,'drag_pair');
  }else drawDrag();
 }else if(!cancel&&geometry)select({kind:'point',index:d.index,endpoint:'top'});
 hoveredPair=null;drawPanorama();
}
dragArea.onpointerup=()=>finishPairDrag();
dragArea.onpointercancel=()=>finishPairDrag(true);
dragArea.onlostpointercapture=()=>finishPairDrag(true);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&pointerDrag){e.preventDefault();finishPairDrag(true);}});
function movePair(from,to){
 const empty=activeSource()?.role==='empty',order=[...(empty?demoOrder:previewOrder)];
 if(!Number.isInteger(from)||from<0||from>=order.length||to<0||to>order.length)return;
 const [item]=order.splice(from,1);order.splice(to>from?to-1:to,0,item);
 if(empty){demoOrder=order;drawDrag();}else setPreviewOrder(order,'drag_pair');
}

 return {refresh(){if(pointerDrag)return;previewOrder=options.getPairs().map((_,i)=>i);geometry=previewOrder.length?{width:1024}:null;drawDrag();},cancel(){finishPairDrag(true);},moveSelected(delta){const i=options.selectedPosition();if(i<0)return;movePair(i,delta<0?Math.max(0,i-1):Math.min(previewOrder.length,i+2));}};
};
