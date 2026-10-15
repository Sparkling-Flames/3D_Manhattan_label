(function(root){
const eps=1e-8,cross=(a,b,p)=>(b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]);
const area=p=>Math.abs(p.reduce((s,a,i)=>{let b=p[(i+1)%p.length];return s+a[0]*b[1]-b[0]*a[1]},0)/2);
function clean(p){return p.filter((a,i)=>!i||Math.hypot(a[0]-p[i-1][0],a[1]-p[i-1][1])>eps).filter((a,i,q)=>i!==q.length-1||Math.hypot(a[0]-q[0][0],a[1]-q[0][1])>eps)}
function inside(p,q){let c=false;for(let i=0,j=q.length-1;i<q.length;j=i++){let a=q[i],b=q[j];if(Math.abs(cross(a,b,p))<eps&&p[0]>=Math.min(a[0],b[0])-eps&&p[0]<=Math.max(a[0],b[0])+eps&&p[1]>=Math.min(a[1],b[1])-eps&&p[1]<=Math.max(a[1],b[1])+eps)return true;if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])c=!c}return c}
function valid(p){if(p.length<3||area(p)<eps||p.some(a=>!a.every(Number.isFinite)))return false;for(let i=0;i<p.length;i++)for(let j=i+1;j<p.length;j++){if(j===i+1||(i===0&&j===p.length-1))continue;let a=p[i],b=p[(i+1)%p.length],c=p[j],d=p[(j+1)%p.length];let c1=cross(a,b,c),c2=cross(a,b,d),c3=cross(c,d,a),c4=cross(c,d,b);if(c1*c2<=eps&&c3*c4<=eps&&Math.max(Math.min(a[0],b[0]),Math.min(c[0],d[0]))<=Math.min(Math.max(a[0],b[0]),Math.max(c[0],d[0]))+eps&&Math.max(Math.min(a[1],b[1]),Math.min(c[1],d[1]))<=Math.min(Math.max(a[1],b[1]),Math.max(c[1],d[1]))+eps)return false}return true}
function clip(poly,a,b,side){if(Math.hypot(a[0]-b[0],a[1]-b[1])<eps)return null;let out=[];for(let i=0;i<poly.length;i++){let p=poly[i],q=poly[(i+1)%poly.length],fp=side*cross(a,b,p),fq=side*cross(a,b,q),ip=fp>=-eps,iq=fq>=-eps;if(ip)out.push(p.slice());if(ip!==iq){let t=fp/(fp-fq);out.push([p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])])}}out=clean(out);return valid(out)?out:null}
function floor(points){return points.filter((_,i)=>i%2).map(([x,y])=>{let u=(x/1024-.5)*2*Math.PI,v=(y/512-.5)*Math.PI,r=1/Math.tan(v);return [r*Math.sin(u),-r*Math.cos(u)]})}
function erp([x,z]){let r=Math.hypot(x,z);return [(Math.atan2(x,-z)/(2*Math.PI)+.5)*1024,(Math.atan2(1,r)/Math.PI+.5)*512]}
function basis(angle){let r=angle*Math.PI/180;return [[Math.cos(r),Math.sin(r)],[-Math.sin(r),Math.cos(r)]]}
function local(p,angle){let [u,v]=basis(angle);return [p[0]*u[0]+p[1]*u[1],p[0]*v[0]+p[1]*v[1]]}
function global(p,angle){let [u,v]=basis(angle);return [p[0]*u[0]+p[1]*v[0],p[0]*u[1]+p[1]*v[1]]}
function orthEnd(a,b,angle){let q=local([b[0]-a[0],b[1]-a[1]],angle);q=Math.abs(q[0])>=Math.abs(q[1])?[q[0],0]:[0,q[1]];let t=global(q,angle);return [a[0]+t[0],a[1]+t[1]]}
function rectangle(a,b,angle){let x=local(a,angle),y=local(b,angle);let p=[[x[0],x[1]],[y[0],x[1]],[y[0],y[1]],[x[0],y[1]]].map(v=>global(v,angle));return valid(p)?p:null}
function rectBounds(poly,angle){let q=poly.map(p=>local(p,angle));return [global([Math.min(...q.map(p=>p[0])),Math.min(...q.map(p=>p[1]))],angle),global([Math.max(...q.map(p=>p[0])),Math.max(...q.map(p=>p[1]))],angle)]}
function intersection(a,b,c,d){let u=[b[0]-a[0],b[1]-a[1]],v=[d[0]-c[0],d[1]-c[1]],den=u[0]*v[1]-u[1]*v[0];if(Math.abs(den)<eps)return null;let t=((c[0]-a[0])*v[1]-(c[1]-a[1])*v[0])/den;return [a[0]+u[0]*t,a[1]+u[1]*t]}
function moveEdge(poly,index,offset){let n=poly.length;if(!Number.isInteger(index)||index<0||index>=n||!Number.isFinite(offset))return null;let a=poly[index],b=poly[(index+1)%n],len=Math.hypot(b[0]-a[0],b[1]-a[1]);if(len<eps)return null;let norm=[-(b[1]-a[1])/len,(b[0]-a[0])/len],c=[a[0]+offset*norm[0],a[1]+offset*norm[1]],d=[b[0]+offset*norm[0],b[1]+offset*norm[1]],aa=intersection(poly[(index+n-1)%n],a,c,d),bb=intersection(b,poly[(index+2)%n],c,d);if(!aa||!bb)return null;let p=poly.map(p=>p.slice());p[index]=aa;p[(index+1)%n]=bb;return valid(p)?p:null}
// Snapping is an editing aid only. Replay consumes resolved coordinates, never GT or zoom.
// A finite overlap is required: the extension of a remote GT edge is not a target.
function edgeSnapCandidates(a,b,reference,tolerance,options={}){
 if(!(tolerance>0)||!Number.isFinite(tolerance))return [];
 const dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy);if(len<eps)return [];
 const u=[dx/len,dy/len],n=[-u[1],u[0]],dot=(p,q)=>p[0]*q[0]+p[1]*q[1],out=[];
 reference.forEach((c,i)=>{const d=reference[(i+1)%reference.length],v=[d[0]-c[0],d[1]-c[1]],vl=Math.hypot(...v);if(vl<eps)return;
  const sine=Math.abs(u[0]*v[1]-u[1]*v[0])/vl;if(sine>Math.sin((options.maxAngleDegrees??.5)*Math.PI/180))return;
  const rel=[c[0]-a[0],c[1]-a[1]],t0=dot(rel,u),dt=dot(v,u),lo=Math.max(0,Math.min(t0,t0+dt)),hi=Math.min(len,Math.max(t0,t0+dt));if(hi-lo<=eps)return;
  const n0=dot(rel,n),dn=dot(v,n),at=t=>n0+(t-t0)/dt*dn,low=at(lo),high=at(hi),distance=Math.max(Math.abs(low),Math.abs(high));if(distance>tolerance)return;
  out.push({gt_edge:i,offset:(low+high)/2,distance,exact:sine<=1e-10,normal:n,overlap:[lo,hi],line_error:Math.abs(high-low)/2});
 });return out.sort((a,b)=>a.distance-b.distance||a.gt_edge-b.gt_edge);
}
function snapRectangle(a,b,angle,reference,tolerance){
 const original=rectangle(a,b,angle);if(!original)return {a:a.slice(),b:b.slice(),polygon:null,matches:[]};
 const x=local(a,angle),y=local(b,angle),selected=original.map((p,i)=>edgeSnapCandidates(p,original[(i+1)%4],reference,tolerance)[0]||null);
 for(let attempt=0;attempt<5;attempt++){
  const xx=x.slice(),yy=y.slice();selected.forEach((s,i)=>{if(!s)return;const p=original[i],q=local([p[0]+s.normal[0]*s.offset,p[1]+s.normal[1]*s.offset],angle);if(i===0)xx[1]=q[1];if(i===1)yy[0]=q[0];if(i===2)yy[1]=q[1];if(i===3)xx[0]=q[0]});
  const aa=global(xx,angle),bb=global(yy,angle),p=rectangle(aa,bb,angle);
  let bad=[];if(!p||(yy[0]-xx[0])*(y[0]-x[0])<=0||(yy[1]-xx[1])*(y[1]-x[1])<=0)bad=selected.map((s,i)=>s?i:-1).filter(i=>i>=0);
  else selected.forEach((s,i)=>{if(s&&!edgeSnapCandidates(p[i],p[(i+1)%4],reference,tolerance).some(c=>c.gt_edge===s.gt_edge))bad.push(i)});
  if(!bad.length)return {a:aa,b:bb,polygon:p,matches:selected.flatMap((s,i)=>s?[{...s,edge:i}]:[])};
  // Never collapse or invert a small rectangle to satisfy conflicting nearby edges.
  bad.sort((i,j)=>selected[j].distance-selected[i].distance);selected[bad[0]]=null;
 }
 return {a:a.slice(),b:b.slice(),polygon:original,matches:[]};
}
// A local GT corner is also a useful stop while extending a cut edge. The
// closest point must be within the screen-space radius of this finite segment.
function vertexSnapCandidates(a,b,reference,tolerance){
 const dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy);if(!(tolerance>0)||!Number.isFinite(tolerance)||len<eps)return [];
 const u=[dx/len,dy/len],normal=[-u[1],u[0]];
 return reference.flatMap((p,i)=>{const rel=[p[0]-a[0],p[1]-a[1]],t=rel[0]*u[0]+rel[1]*u[1],along=Math.max(0,Math.min(len,t)),distance=Math.hypot(rel[0]-along*u[0],rel[1]-along*u[1]);return distance<=tolerance?[{kind:'vertex',gt_vertex:i,offset:rel[0]*normal[0]+rel[1]*normal[1],distance,normal,exact:false}]:[]}).sort((a,b)=>a.distance-b.distance||a.gt_vertex-b.gt_vertex);
}
function snapEdgeMove(poly,index,offset,reference,tolerance,options={}){
 const p=moveEdge(poly,index,offset);if(!p)return {offset,polygon:null,matches:[]};
 const sameTarget=(a,b)=>a&&b&&(a.kind==='vertex'||b.kind==='vertex'?a.kind===b.kind&&a.gt_vertex===b.gt_vertex:a.gt_edge===b.gt_edge);
 const radius=options.preferred?Math.max(tolerance,options.releaseTolerance||tolerance):tolerance;
 const collect=q=>[...edgeSnapCandidates(q[index],q[(index+1)%q.length],reference,radius,{maxAngleDegrees:5}),...vertexSnapCandidates(q[index],q[(index+1)%q.length],reference,radius)];
 const all=collect(p),preferred=all.find(s=>sameTarget(s,options.preferred)),candidates=[...(preferred?[preferred]:[]),...all.filter(s=>s.distance<=tolerance&&!sameTarget(s,preferred))];
 const a=poly[index],b=poly[(index+1)%poly.length],len=Math.hypot(b[0]-a[0],b[1]-a[1]),n=[-(b[1]-a[1])/len,(b[0]-a[0])/len];
 for(const s of candidates){const resolved=offset+s.offset*(n[0]*s.normal[0]+n[1]*s.normal[1]),q=moveEdge(poly,index,resolved);if(q&&[index,(index+1)%q.length].every(i=>Math.hypot(q[i][0]-p[i][0],q[i][1]-p[i][1])<=2*radius)&&collect(q).some(c=>sameTarget(c,s)))return {offset:resolved,polygon:q,matches:[{...s,edge:index,held:s.distance>tolerance}]}}
 return {offset,polygon:p,matches:[]};
}
function boundaryQuad(lines){
 if(!Array.isArray(lines)||lines.length!==4||lines.some(l=>!Array.isArray(l)||l.length!==2||l.some(p=>!Array.isArray(p)||p.length!==2||!p.every(Number.isFinite))))return null;
 const p=lines.map((l,i)=>intersection(...lines[(i+3)%4],...l));if(p.some(q=>!q)||!valid(p))return null;
 const turns=p.map((a,i)=>cross(a,p[(i+1)%4],p[(i+2)%4]));return turns.every(t=>t>eps)||turns.every(t=>t< -eps)?p:null;
}
function followRectangleGT(poly,reference,matches,tolerance){
 if(poly?.length!==4||!valid(poly)||!matches.length)return null;
 const lines=poly.map((a,i)=>[a.slice(),poly[(i+1)%4].slice()]);
 for(const m of matches){if(!Number.isInteger(m.edge)||m.edge<0||m.edge>3||!Number.isInteger(m.gt_edge)||m.gt_edge<0||m.gt_edge>=reference.length)return null;lines[m.edge]=[reference[m.gt_edge].slice(),reference[(m.gt_edge+1)%reference.length].slice()]}
 const polygon=boundaryQuad(lines);if(!polygon||polygon.some((p,i)=>Math.hypot(p[0]-poly[i][0],p[1]-poly[i][1])>tolerance))return null;
 const resolved=[];for(const m of matches){const s=edgeSnapCandidates(polygon[m.edge],polygon[(m.edge+1)%4],reference,tolerance).find(s=>s.gt_edge===m.gt_edge&&s.exact);if(!s)return null;resolved.push({...s,edge:m.edge})}
 return {lines,polygon,matches:resolved};
}
function edgeAngle(poly,index){const a=poly[index],b=poly[(index+1)%poly.length];if(!a||!b)return 0;const angle=Math.atan2(b[1]-a[1],b[0]-a[0])*180/Math.PI;return ((angle+45)%90+90)%90-45}
function replay(poly,ops){let p=poly.map(x=>x.slice());for(let o of ops){if(o.type==='cut'&&[1,-1].includes(o.side))p=clip(p,o.a,o.b,o.side);else if(o.type==='rectangle'&&Number.isFinite(o.angle))p=rectangle(o.a,o.b,o.angle);else if(o.type==='edge_move')p=moveEdge(p,o.index,o.offset);else if(o.type==='gt_follow')p=boundaryQuad(o.lines);else return null;if(!p||!valid(p))return null}return p}
const api={cross,area,inside,valid,clip,floor,erp,basis,local,global,orthEnd,rectangle,rectBounds,moveEdge,edgeSnapCandidates,vertexSnapCandidates,snapRectangle,snapEdgeMove,boundaryQuad,followRectangleGT,edgeAngle,replay};if(typeof module!=='undefined')module.exports=api;else root.Geo=api;
})(typeof window==='undefined'?globalThis:window);
