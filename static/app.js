const PAGE=document.body.dataset.page;
const IS_MEMBER=document.body.dataset.member==='1';
const CATS=[['all','✨','Tout'],['pain','🥖','Pain'],['sucre','🍚','Sucre'],['eau','💧','Dlo'],['food','🍛','Manje'],['gas','🔥','Gaz'],['taxi','🚕','Taxi'],['other','📦','Autres']];
let products=[],cart=[],activeCat='all',orders=[],ads=[],members=[],drivers=[],resetRequests=[];

const fmt=n=>new Intl.NumberFormat('fr-FR').format(Number(n||0))+' Gdes';
function toast(m){const t=document.getElementById('toast');if(!t)return;t.textContent=m;t.style.display='block';setTimeout(()=>t.style.display='none',2200)}
async function api(url,opt={}){const r=await fetch(url,{headers:{'Content-Type':'application/json'},...opt});let data={};try{data=await r.json()}catch(e){}if(!r.ok)throw data;return data}
function statusClass(s){return s==='Nouveau'?'new':s==='Préparation'?'prep':s==='En route'?'route':s==='Livré'?'done':'cancel'}
function itemsText(o){return (o.items||[]).map(i=>`${i.icon||''} ${i.name} × ${i.qty}`).join('<br>')}
function esc(s){return String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}

function selectPayment(method,btn){
  const payment=document.getElementById('payment'); if(!payment)return;
  payment.value=method;document.querySelectorAll('.pay-btn').forEach(b=>b.classList.remove('active'));if(btn)btn.classList.add('active');
  const info=document.getElementById('paymentInfo'),box=document.getElementById('transactionBox');
  if(method==='Cash'){info.innerHTML='💵 Peman an ap fèt Cash.';box.style.display='none';document.getElementById('transactionId').value='';const pa=document.getElementById('paidAmount');if(pa)pa.value='';}
  else if(method==='MonCash'){info.innerHTML='📱 <b>MonCash:</b> +(509) 3414-6480 — Voye peman an sou MonCash.';box.style.display='block';}
  else{info.innerHTML='📱 <b>NatCash:</b> +(509) 3390-3940 — Voye peman an sou NatCash.';box.style.display='block';}
}

if(PAGE==='login')toggleLoginRole();
if(PAGE==='client')initClient();
if(PAGE==='admin')initAdmin();
if(PAGE==='driver')initDriver();

async function initClient(){
  try{products=await api('/api/products');ads=await api('/api/ads');renderAds();renderCats();renderProducts();if(IS_MEMBER){renderCart();await loadMyOrders();}}catch(e){toast('Gen yon pwoblèm pou chaje paj la')}
}
function renderAds(){
  const el=document.getElementById('ads');if(!el)return;
  el.innerHTML=ads.length?ads.map(a=>`<article class="adCard">${a.image_url?`<img src="${esc(a.image_url)}" alt="${esc(a.title)}" onerror="this.style.display='none'">`:'<div class="adPlaceholder">📣</div>'}<div class="adBody"><h3>${esc(a.title)}</h3><p>${esc(a.description)}</p>${a.target_url?`<a href="${esc(a.target_url)}" target="_blank" rel="noopener">Wè plis →</a>`:''}</div></article>`).join(''):'<div class="muted">Pa gen anons aktif kounye a.</div>';
}
function renderCats(){const el=document.getElementById('cats');if(!el)return;el.innerHTML=CATS.map(c=>`<div class="cat ${activeCat===c[0]?'active':''}" onclick="setCat('${c[0]}')"><span>${c[1]}</span><b>${c[2]}</b></div>`).join('')}
function setCat(c){activeCat=c;renderCats();renderProducts()}
function renderProducts(){const el=document.getElementById('products');if(!el)return;const list=products.filter(p=>activeCat==='all'||p.category===activeCat);el.innerHTML=list.map(p=>`<div class="product"><div class="pico">${p.icon}</div><div class="pmeta"><b>${esc(p.name)}</b><small>${esc(p.description||'')}</small><strong>${p.price?fmt(p.price):'Pri sou demann'}</strong></div>${IS_MEMBER?`<button onclick="addCart(${p.id})">+</button>`:'<a class="miniLogin" href="/login">Konekte</a>'}</div>`).join('')}
function addCart(id){const p=products.find(x=>x.id===id),f=cart.find(x=>x.id===id);if(!p)return;if(f)f.qty++;else cart.push({...p,qty:1});renderCart();toast('Ajoute nan panier')}
function qty(id,d){const f=cart.find(x=>x.id===id);if(!f)return;f.qty+=d;if(f.qty<=0)cart=cart.filter(x=>x.id!==id);renderCart()}
function syncFee(){document.getElementById('fee').value=document.getElementById('zone').value;renderCart()}
function renderCart(){const el=document.getElementById('cart');if(!el)return;el.innerHTML=cart.length?cart.map(i=>`<div class="cartrow"><span>${i.icon} <b>${esc(i.name)}</b><br><small>${i.price?fmt(i.price):'Pri pou konfime'}</small></span><span><button class="qbtn" onclick="qty(${i.id},-1)">−</button> <b>${i.qty}</b> <button class="qbtn" onclick="qty(${i.id},1)">+</button></span></div>`).join(''):'<div class="muted">Panier la vid.</div>';const subtotal=cart.reduce((s,i)=>s+Number(i.price)*i.qty,0),fee=Number(document.getElementById('fee')?.value||0);document.getElementById('total').textContent=fmt(subtotal+fee)}
async function submitOrder(){
  if(!IS_MEMBER)return location.href='/login';
  const payment=document.getElementById('payment').value,transaction_id=document.getElementById('transactionId').value.trim(),paid_amount=Number((document.getElementById('paidAmount')||{}).value||0);
  if(!cart.length)return alert('Ajoute omwen yon pwodwi nan panier la.');
  if(!document.getElementById('address').value.trim())return alert('Ranpli adrès livrezon an.');
  if((payment==='MonCash'||payment==='NatCash')&&!transaction_id)return alert('Antre nimewo tranzaksyon an.');if((payment==='MonCash'||payment==='NatCash')&&paid_amount<=0)return alert('Antre montan ou peye a.');
  const payload={address:document.getElementById('address').value.trim(),landmark:document.getElementById('landmark').value.trim(),zone:document.getElementById('zone').selectedOptions[0].text,delivery_fee:Number(document.getElementById('fee').value||0),payment,transaction_id,paid_amount,note:document.getElementById('note').value.trim(),order_type:'Livraison',items:cart.map(i=>({name:i.name,qty:i.qty,price:i.price,icon:i.icon}))};
  try{const r=await api('/api/orders',{method:'POST',body:JSON.stringify(payload)});document.getElementById('success').innerHTML=`<div class="success">✅ Kòmand lan antre! Nimewo ou se <b>${r.code}</b>. Total: <b>${fmt(r.total)}</b>. Ou ka swiv li nan “Kòmand mwen yo”.</div>`;cart=[];renderCart();document.getElementById('transactionId').value='';const pa=document.getElementById('paidAmount');if(pa)pa.value='';await loadMyOrders();toast('Kòmand valide')}catch(e){alert(e.error==='member_login_required'?'Konekte kòm manm anvan.':'Kòmand lan pa pase. Verifye enfòmasyon yo.')}
}
async function loadMyOrders(){
  const el=document.getElementById('myOrdersList');if(!el)return;
  try{const mine=await api('/api/my-orders');el.innerHTML=mine.length?mine.map(o=>`<div class="myOrderCard"><div class="myOrderTop"><b>${o.code}</b><span class="badge ${statusClass(o.status)}">${o.status}</span></div><div class="progressTrack">${['Nouveau','Préparation','En route','Livré'].map((s,idx)=>`<span class="${stageReached(o.status,s)?'reached':''}">${idx+1}<small>${s}</small></span>`).join('')}</div><p>${itemsText(o)}</p><div class="orderMeta"><span><b>${fmt(o.total)}</b></span><span>${o.payment}${o.payment!=='Cash'?` — ${o.payment_status}`:''}</span><span>${o.driver?'🛵 '+esc(o.driver):'Livreur poko asiyen'}</span></div></div>`).join(''):'<div class="muted">Ou poko gen kòmand.</div>';}catch(e){el.innerHTML='<div class="muted">Pa ka chaje kòmand yo.</div>'}
}
function stageReached(current,stage){const a=['Nouveau','Préparation','En route','Livré'];if(current==='Annulé')return false;return a.indexOf(stage)<=a.indexOf(current)}

async function initAdmin(){await reloadAdmin()}
async function reloadAdmin(){
  products=await api('/api/products');orders=await api('/api/orders');members=await api('/api/members');drivers=await api('/api/admin/drivers');resetRequests=await api('/api/admin/password-resets');const st=await api('/api/stats');const ds=await api('/api/driver-stats');ads=await api('/api/admin/ads');const summary=await api('/api/admin/summary');
  document.getElementById('sNew').textContent=st.Nouveau?.count||0;document.getElementById('sPrep').textContent=st['Préparation']?.count||0;document.getElementById('sRoute').textContent=st['En route']?.count||0;document.getElementById('sDone').textContent=st['Livré']?.count||0;document.getElementById('sRevenue').textContent=fmt(st.revenue_delivered||0);document.getElementById('sMembers').textContent=st.members||0;
  const mt=document.getElementById('sMembersToday'),mw=document.getElementById('sMembersWeek'),mm=document.getElementById('sMembersMonth'),mt2=document.getElementById('sMembersTotal2');
  if(mt)mt.textContent=st.members_today||0;if(mw)mw.textContent=st.members_week||0;if(mm)mm.textContent=st.members_month||0;if(mt2)mt2.textContent=st.members||0;
  renderMembers();renderDriverAccounts();renderResetRequests();renderDriverStats(ds);renderAdsAdmin();renderAdminProducts();populateDriverFilters();renderOrders();renderAdminSummary(summary);await loadFinance();
}
function renderAdminSummary(r){
  const set=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=v};
  set('rOrdersToday',r.orders_today||0);set('rActiveToday',r.active_today||0);set('rDeliveredToday',r.delivered_today||0);
  set('rRevenueToday',fmt(r.delivered_revenue_today||0));set('rMonCash',fmt(r.moncash?.amount||0));set('rMonCashCount',(r.moncash?.count||0)+' tranzaksyon');
  set('rNatCash',fmt(r.natcash?.amount||0));set('rNatCashCount',(r.natcash?.count||0)+' tranzaksyon');
}

async function loadFinance(){
  const period=document.getElementById('financePeriod')?.value||'today';
  const r=await api('/api/admin/finance?period='+encodeURIComponent(period));
  const set=(id,v)=>{const el=document.getElementById(id);if(el)el.textContent=v};
  set('fCash',fmt(r.cash?.amount||0));set('fCashCount',(r.cash?.count||0)+' tranzaksyon');
  set('fMonCash',fmt(r.moncash?.amount||0));set('fMonCashCount',(r.moncash?.count||0)+' tranzaksyon');
  set('fNatCash',fmt(r.natcash?.amount||0));set('fNatCashCount',(r.natcash?.count||0)+' tranzaksyon');
  set('fSales',fmt(r.sales_total||0));set('fDelivered',(r.delivered_count||0)+' livré');
}
function populateDriverFilters(){
  const filter=document.getElementById('orderDriverFilter');if(!filter)return;
  const current=filter.value;
  filter.innerHTML='<option value="">Tout livreur</option>'+drivers.filter(d=>d.active).map(d=>`<option value="${esc(d.name)}">${esc(d.name)}</option>`).join('');
  filter.value=current;
}
function renderDriverAccounts(){
  const box=document.getElementById('driverAccounts');if(!box)return;
  box.innerHTML=drivers.length?drivers.map(d=>`<div class="driverAccountRow"><div><b>${esc(d.name)}</b><small>${d.active?'🟢 Aktif':'⚪ Dezaktive'}</small></div><div class="driverAccountActions"><button onclick="resetDriverPassword(${d.id})">🔐 Chanje modpas</button><button class="${d.active?'removeBtn':'saveBtn'}" onclick="toggleDriverAccount(${d.id},${!d.active})">${d.active?'Dezaktive':'Aktive'}</button></div></div>`).join(''):'<div class="muted">Pa gen kont livreur.</div>';
}
async function addDriverAccount(){
  const name=document.getElementById('newDriverName').value.trim(),password=document.getElementById('newDriverPassword').value;
  if(!name||password.length<6)return alert('Mete non livreur ak yon modpas omwen 6 karaktè.');
  await api('/api/admin/drivers',{method:'POST',body:JSON.stringify({name,password})});
  document.getElementById('newDriverName').value='';document.getElementById('newDriverPassword').value='';
  await reloadAdmin();toast('Kont livreur ajoute');
}
async function toggleDriverAccount(id,active){await api('/api/admin/drivers/'+id,{method:'PATCH',body:JSON.stringify({active})});await reloadAdmin()}
async function resetDriverPassword(id){
  const password=prompt('Mete nouvo modpas livreur la (omwen 6 karaktè):');if(!password)return;
  if(password.length<6)return alert('Modpas la twò kout.');
  await api('/api/admin/drivers/'+id,{method:'PATCH',body:JSON.stringify({password})});toast('Modpas livreur chanje');
}
function renderResetRequests(){
  const box=document.getElementById('passwordResetRequests');if(!box)return;
  const pending=resetRequests.filter(r=>r.status==='En attente');
  box.innerHTML=pending.length?pending.map(r=>`<div class="resetRequestRow"><div><b>@${esc(r.username)}</b><small>📞 ${esc(r.phone)} · ${esc((r.created_at||'').replace('T',' '))}</small></div><button onclick="resolveResetRequest(${r.id})">Bay modpas tanporè</button></div>`).join(''):'<div class="muted">Pa gen demann reset kounye a.</div>';
}
async function resolveResetRequest(id){
  const password=prompt('Mete yon modpas tanporè pou manm nan (omwen 8 karaktè):');if(!password)return;
  if(password.length<8)return alert('Modpas la dwe gen omwen 8 karaktè.');
  await api('/api/admin/password-resets/'+id+'/resolve',{method:'POST',body:JSON.stringify({password})});
  await reloadAdmin();toast('Demann reset rezoud');
}
function renderMembers(){
  const box=document.getElementById('membersList');if(!box)return;
  const q=(document.getElementById('memberSearch')?.value||'').trim().toLowerCase();
  const list=members.filter(m=>!q||[m.full_name,m.username,m.phone].some(v=>String(v||'').toLowerCase().includes(q)));
  box.innerHTML=list.length?list.map(m=>`<tr><td><b>${esc(m.full_name)}</b><br><small>#${m.id}</small></td><td>@${esc(m.username)}</td><td>${esc(m.phone)}</td><td><small>${esc((m.created_at||'').replace('T',' '))}</small></td><td><b>${m.orders_count}</b></td><td>${m.delivered_count}</td><td>${fmt(m.orders_total)}</td></tr>`).join(''):'<tr><td colspan="7">Pa jwenn manm.</td></tr>';
}
function renderDriverStats(ds){const box=document.getElementById('driverStats');if(!box)return;box.innerHTML=ds.map(d=>`<div class="driverStatCard"><strong>${esc(d.driver)}</strong><span>${d.count} livrezon</span><b>${fmt(d.total)}</b></div>`).join('')}
function renderAdminProducts(){const box=document.getElementById('productManager');if(!box)return;box.innerHTML=products.map(p=>`<div class="productEditRow"><div class="editIcon">${p.icon}</div><div class="editFields"><input id="pn-${p.id}" value="${esc(p.name)}" aria-label="Non pwodwi"><input id="pp-${p.id}" type="number" min="0" value="${Number(p.price||0)}" aria-label="Pri"></div><div class="editActions"><button class="saveBtn" onclick="saveProduct(${p.id})">💾 Sove</button><button class="removeBtn" onclick="delProduct(${p.id})">Retire</button></div></div>`).join('')}
async function saveProduct(id){const name=document.getElementById('pn-'+id).value.trim(),price=Number(document.getElementById('pp-'+id).value||0);if(!name)return alert('Mete non pwodwi a.');await api('/api/products/'+id,{method:'PUT',body:JSON.stringify({name,price})});await reloadAdmin();toast('Pwodwi mete ajou')}
async function addProduct(){const name=document.getElementById('pname').value.trim();if(!name)return alert('Mete non pwodwi a');await api('/api/products',{method:'POST',body:JSON.stringify({name,price:Number(document.getElementById('pprice').value||0),category:document.getElementById('pcat').value,icon:document.getElementById('picon').value||'📦'})});document.getElementById('pname').value='';await reloadAdmin();toast('Pwodwi ajoute')}
async function delProduct(id){await api('/api/products/'+id,{method:'DELETE'});await reloadAdmin()}

function renderAdsAdmin(){const box=document.getElementById('adManager');if(!box)return;box.innerHTML=ads.length?ads.map(a=>`<div class="adAdminRow"><div>${a.image_url?`<img src="${esc(a.image_url)}" alt="">`:'📣'}</div><div><b>${esc(a.title)}</b><small>${esc(a.description)}</small><small>${a.starts_at||'Kounye a'} → ${a.ends_at||'San dat fen'}</small></div><div><button class="${a.active?'saveBtn':''}" onclick="toggleAd(${a.id},${!a.active})">${a.active?'Aktif':'Aktive'}</button><button class="removeBtn" onclick="removeAd(${a.id})">Efase</button></div></div>`).join(''):'<div class="muted">Pa gen anons.</div>'}
async function addAd(){const title=document.getElementById('adTitle').value.trim();if(!title)return alert('Mete tit anons lan');const payload={title,description:document.getElementById('adDescription').value.trim(),image_url:document.getElementById('adImage').value.trim(),target_url:document.getElementById('adLink').value.trim(),starts_at:document.getElementById('adStart').value,ends_at:document.getElementById('adEnd').value,active:true};await api('/api/admin/ads',{method:'POST',body:JSON.stringify(payload)});['adTitle','adDescription','adImage','adLink','adStart','adEnd'].forEach(id=>document.getElementById(id).value='');await reloadAdmin();toast('Anons ajoute')}
async function toggleAd(id,active){await api('/api/admin/ads/'+id,{method:'PATCH',body:JSON.stringify({active})});await reloadAdmin()}
async function removeAd(id){if(confirm('Efase anons sa?')){await api('/api/admin/ads/'+id,{method:'DELETE'});await reloadAdmin()}}

function paymentAmountInfo(o){
  if(o.payment==='Cash')return '<span class="cashPayBadge">💵 Cash</span>';
  const paid=Number(o.paid_amount||0),total=Number(o.total||0),diff=paid-total;
  let cls='payMatch',label='✅ Montan OK';
  if(diff < -0.01){cls='payShort';label='⚠️ Manke '+fmt(Math.abs(diff));}
  else if(diff > 0.01){cls='payOver';label='ℹ️ Depase '+fmt(diff);}
  return `<div class="paymentAdminBox"><b>${esc(o.payment)}</b><span>Total: ${fmt(total)}</span><span class="paidLine">Peye: <strong>${fmt(paid)}</strong></span>${o.transaction_id?`<span>Tx: ${esc(o.transaction_id)}</span>`:''}<span class="${cls}">${label}</span><span>${esc(o.payment_status||'')}</span></div>`;
}
function renderOrders(){
  const box=document.getElementById('orders');if(!box)return;
  const q=(document.getElementById('orderSearch')?.value||'').trim().toLowerCase();
  const sf=document.getElementById('orderStatusFilter')?.value||'';
  const pf=document.getElementById('orderPaymentFilter')?.value||'';
  const df=document.getElementById('orderDriverFilter')?.value||'';
  const list=orders.filter(o=>{
    const mq=!q||[o.code,o.customer,o.phone,o.address].some(v=>String(v||'').toLowerCase().includes(q));
    return mq&&(!sf||o.status===sf)&&(!pf||o.payment===pf)&&(!df||o.driver===df);
  });
  const activeDrivers=drivers.filter(d=>d.active);
  box.innerHTML=list.length?list.map(o=>`<tr><td><b>${o.code}</b><br><small>${o.created_at}</small></td><td><b>${esc(o.customer)}</b><br>${esc(o.phone)}${o.customer_id?'<br><small>👤 Manm #'+o.customer_id+'</small>':''}</td><td>${itemsText(o)}${o.note?'<br><small>📝 '+esc(o.note)+'</small>':''}</td><td><b>${fmt(o.total)}</b><br><small>Fee ${fmt(o.delivery_fee)}</small>${paymentAmountInfo(o)}</td><td>${esc(o.address)}${o.landmark?'<br><small>📌 '+esc(o.landmark)+'</small>':''}</td><td><span class="badge ${statusClass(o.status)}">${o.status}</span><br><select onchange="patchOrder(${o.id},'status',this.value)">${['Nouveau','Préparation','En route','Livré','Annulé'].map(s=>`<option ${s===o.status?'selected':''}>${s}</option>`).join('')}</select></td><td><select onchange="patchOrder(${o.id},'driver',this.value)"><option value="">Non assigné</option>${activeDrivers.map(d=>`<option ${d.name===o.driver?'selected':''}>${esc(d.name)}</option>`).join('')}</select></td><td>${o.payment!=='Cash'?`<button class="saveBtn" onclick="paymentStatus(${o.id},'Konfime')">Konfime</button> <button class="removeBtn" onclick="paymentStatus(${o.id},'Refize')">Refize</button><br><br>`:''}<button onclick="copyOrderSummaryById(${o.id})">📋 Mesaj</button> <button onclick="deleteOrder(${o.id})">Efase</button></td></tr>`).join(''):'<tr><td colspan="8">Pa gen kòmand ki koresponn ak filtè yo.</td></tr>';
}
async function patchOrder(id,key,val){await api('/api/orders/'+id,{method:'PATCH',body:JSON.stringify({[key]:val})});await reloadAdmin();toast('Mete ajou')}
async function paymentStatus(id,status){await api('/api/orders/'+id,{method:'PATCH',body:JSON.stringify({payment_status:status})});await reloadAdmin();toast('Peman '+status.toLowerCase())}
async function deleteOrder(id){if(confirm('Efase kòmand sa?')){await api('/api/orders/'+id,{method:'DELETE'});await reloadAdmin()}}

async function initDriver(){await loadDriver()}
function phoneDigits(v){return String(v||'').replace(/\D/g,'')}
function waPhone(v){let d=phoneDigits(v);if(d.length===8)d='509'+d;return d}
async function loadDriver(){
  const stats=await api('/api/driver/me-stats');
  const a=document.getElementById('dActive'),d=document.getElementById('dDelivered'),t=document.getElementById('dDeliveredTotal'),cr=document.getElementById('dCashCollected');
  if(a)a.textContent=stats.active||0;if(d)d.textContent=stats.delivered||0;if(t)t.textContent=fmt(stats.delivered_total||0);if(cr)cr.textContent=fmt(stats.cash_collected||0);
  orders=await api('/api/driver/orders');
  const box=document.getElementById('driverOrders');
  if(!box)return;
  box.innerHTML=orders.length?orders.map(o=>`<div class="driverCard">
    <div class="driverCardTop"><h3>${o.code}</h3><span class="badge ${statusClass(o.status)}">${o.status}</span></div>
    <div class="driverCustomer"><b>👤 ${esc(o.customer)}</b><span>📞 ${esc(o.phone)}</span></div>
    <p class="driverAddress">📍 ${esc(o.address)}${o.landmark?'<br><small>Referans: '+esc(o.landmark)+'</small>':''}</p>
    <div class="driverItems">${itemsText(o)}</div>
    <div class="driverPayment"><span><b>${fmt(o.total)}</b></span><span>${esc(o.payment)}${o.payment!=='Cash'?' — '+esc(o.payment_status||''):''}</span></div>
    ${o.payment==='Cash'?`<div class="cashReceiveBox"><label>💵 Cash resevwa</label><div><input id="cash-${o.id}" type="number" min="0" step="1" value="${o.cash_received||0}" placeholder="${o.total}"><button onclick="saveDriverCash(${o.id})">Anrejistre</button></div></div>`:''}
    <div class="driverContactActions">
      <a class="driverLink call" href="tel:${phoneDigits(o.phone)}">📞 Rele kliyan</a>
      <a class="driverLink whatsapp" target="_blank" rel="noopener" href="https://wa.me/${waPhone(o.phone)}?text=${encodeURIComponent('Bonjou '+o.customer+', se '+stats.driver+' nan Promo Delivery pou kòmand '+o.code+'.')}">💬 WhatsApp</a>
    </div>
    <div class="driverStatusActions">
      ${o.status==='Nouveau'?`<button class="prepAction" onclick="driverStatus(${o.id},'Préparation')">📦 Mwen pran kòmand lan</button>`:''}
      ${o.status!=='En route'&&o.status!=='Livré'?`<button class="routeAction" onclick="driverStatus(${o.id},'En route')">🛵 Mwen sou wout</button>`:''}
      <button class="doneAction" onclick="driverStatus(${o.id},'Livré')">✅ Livrezon fèt</button>
    </div>
  </div>`).join(''):'<div class="card emptyDriver"><b>✅ Pa gen kòmand aktif pou ou.</b><p>Nouvo kòmand Admin asiyen avè w ap parèt isit la.</p></div>';
}
async function saveDriverCash(id){
  const el=document.getElementById('cash-'+id);if(!el)return;
  const amount=Number(el.value||0);
  await api('/api/driver/orders/'+id+'/cash',{method:'POST',body:JSON.stringify({amount})});
  toast('Cash resevwa anrejistre');await loadDriver();
}
async function driverStatus(id,status){
  if(status==='Livré'&&!confirm('Konfime livrezon sa fèt?'))return;
  await api('/api/orders/'+id,{method:'PATCH',body:JSON.stringify({status})});
  await loadDriver();toast('Estati mete ajou: '+status)
}
function copyOrderSummaryById(id){const o=orders.find(x=>x.id===id);if(!o)return;const txt=`PROMO DELIVERY\nKòmand: ${o.code}\nKliyan: ${o.customer}\nTelefòn: ${o.phone}\nAdrès: ${o.address}${o.landmark?' - '+o.landmark:''}\nAtik: ${o.items.map(i=>i.name+' x'+i.qty).join(', ')}\nTotal: ${fmt(o.total)}\nPeman: ${o.payment}${o.transaction_id?' / Tx: '+o.transaction_id:''}${o.payment!=='Cash'?' / Peye: '+fmt(o.paid_amount||0)+' / '+o.payment_status:''}\nEstati: ${o.status}`;if(navigator.clipboard)navigator.clipboard.writeText(txt).then(()=>toast('Mesaj kòmand lan kopye'));else prompt('Kopye mesaj sa:',txt)}
function toggleLoginRole(){const role=document.getElementById('loginRole'),user=document.getElementById('loginUser');if(!role||!user)return;if(role.value==='driver')user.placeholder='Jeff / Duckens / Jn Fritz';else if(role.value==='admin')user.placeholder='admin';else user.placeholder='username manm ou'}

function notifyOrderChanges(list){
  try{
    const key='promoLastStatuses';
    const prev=JSON.parse(localStorage.getItem(key)||'{}');
    const next={};
    (list||[]).forEach(o=>{
      next[o.id]=o.status;
      if(prev[o.id] && prev[o.id]!==o.status){
        const msg=`Kòmand ${o.code}: ${o.status}`;
        toast('🔔 '+msg);
        if('Notification' in window && Notification.permission==='granted') new Notification('Promo Delivery',{body:msg});
      }
    });
    localStorage.setItem(key,JSON.stringify(next));
  }catch(e){}
}
async function enablePromoNotifications(){
  if('Notification' in window && Notification.permission==='default'){
    try{await Notification.requestPermission()}catch(e){}
  }
}
