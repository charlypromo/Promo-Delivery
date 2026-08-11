
const PAGE=document.body.dataset.page;
const CATS=[['all','✨','Tout'],['pain','🥖','Pain'],['sucre','🍚','Sucre'],['eau','💧','Dlo'],['food','🍛','Manje'],['gas','🔥','Gaz'],['taxi','🚕','Taxi'],['other','📦','Autres']];
let products=[],cart=[],activeCat='all',orders=[];

const fmt=n=>new Intl.NumberFormat('fr-FR').format(Number(n||0))+' Gdes';
function toast(m){const t=document.getElementById('toast');t.textContent=m;t.style.display='block';setTimeout(()=>t.style.display='none',2200)}
async function api(url,opt={}){const r=await fetch(url,{headers:{'Content-Type':'application/json'},...opt});if(!r.ok)throw await r.json();return r.json()}
function statusClass(s){return s==='Nouveau'?'new':s==='Préparation'?'prep':s==='En route'?'route':s==='Livré'?'done':'cancel'}
function itemsText(o){return o.items.map(i=>`${i.icon||''} ${i.name} × ${i.qty}`).join('<br>')}
function selectPayment(method,btn){
  const payment=document.getElementById('payment'); if(!payment)return;
  payment.value=method;
  document.querySelectorAll('.pay-btn').forEach(b=>b.classList.remove('active'));
  if(btn)btn.classList.add('active');
  const info=document.getElementById('paymentInfo'), box=document.getElementById('transactionBox');
  if(method==='Cash'){
    info.innerHTML='💵 Peman an ap fèt Cash.';
    box.style.display='none';
    document.getElementById('transactionId').value='';
  }else if(method==='MonCash'){
    info.innerHTML='📱 <b>MonCash:</b> +(509) 3414-6480 — Voye peman an sou MonCash.';
    box.style.display='block';
  }else{
    info.innerHTML='📱 <b>NatCash:</b> +(509) 3390-3940 — Voye peman an sou NatCash.';
    box.style.display='block';
  }
}

if(PAGE==='login') toggleLoginRole();
if(PAGE==='client') initClient();
if(PAGE==='admin') initAdmin();
if(PAGE==='driver') initDriver();

async function initClient(){
  products=await api('/api/products'); renderCats(); renderProducts(); renderCart();
}
function renderCats(){
  document.getElementById('cats').innerHTML=CATS.map(c=>`<div class="cat ${activeCat===c[0]?'active':''}" onclick="setCat('${c[0]}')"><span>${c[1]}</span><b>${c[2]}</b></div>`).join('');
}
function setCat(c){activeCat=c;renderCats();renderProducts()}
function renderProducts(){
  const list=products.filter(p=>activeCat==='all'||p.category===activeCat);
  document.getElementById('products').innerHTML=list.map(p=>`<div class="product"><div class="pico">${p.icon}</div><div class="pmeta"><b>${p.name}</b><small>${p.description||''}</small><strong>${p.price?fmt(p.price):'Pri sou demann'}</strong></div><button onclick="addCart(${p.id})">+</button></div>`).join('');
}
function addCart(id){const p=products.find(x=>x.id===id),f=cart.find(x=>x.id===id);if(f)f.qty++;else cart.push({...p,qty:1});renderCart();toast('Ajoute nan panier')}
function qty(id,d){const f=cart.find(x=>x.id===id);if(!f)return;f.qty+=d;if(f.qty<=0)cart=cart.filter(x=>x.id!==id);renderCart()}
function syncFee(){document.getElementById('fee').value=document.getElementById('zone').value;renderCart()}
function renderCart(){
  const el=document.getElementById('cart'); if(!el)return;
  el.innerHTML=cart.length?cart.map(i=>`<div class="cartrow"><span>${i.icon} <b>${i.name}</b><br><small>${i.price?fmt(i.price):'Pri pou konfime'}</small></span><span><button class="qbtn" onclick="qty(${i.id},-1)">−</button> <b>${i.qty}</b> <button class="qbtn" onclick="qty(${i.id},1)">+</button></span></div>`).join(''):'<div class="muted">Panier la vid.</div>';
  const subtotal=cart.reduce((s,i)=>s+Number(i.price)*i.qty,0),fee=Number(document.getElementById('fee').value||0);
  document.getElementById('total').textContent=fmt(subtotal+fee);
}
async function submitOrder(){
  if(!cart.length)return alert('Ajoute omwen yon pwodwi.');
  const payload={
    customer:document.getElementById('name').value.trim(),phone:document.getElementById('phone').value.trim(),
    address:document.getElementById('address').value.trim(),landmark:document.getElementById('landmark').value.trim(),
    zone:document.getElementById('zone').selectedOptions[0].text,payment:document.getElementById('payment').value,
    transaction_id:(document.getElementById('transactionId')?.value||'').trim(),
    note:document.getElementById('note').value.trim(),order_type:'Livraison',
    delivery_fee:Number(document.getElementById('fee').value||0),
    items:cart.map(i=>({name:i.name,qty:i.qty,price:i.price,icon:i.icon}))
  };
  if(!payload.customer||!payload.phone||!payload.address)return alert('Ranpli non, telefòn ak adrès.');
  if(['MonCash','NatCash'].includes(payload.payment) && !payload.transaction_id)return alert('Antre nimewo tranzaksyon an.');
  const r=await api('/api/orders',{method:'POST',body:JSON.stringify(payload)});
  document.getElementById('success').innerHTML=`<div class="success">✅ Kòmand lan antre! Nimewo ou se <b>${r.code}</b>. Total: <b>${fmt(r.total)}</b>. Kenbe nimewo sa pou swivi.</div>`;
  cart=[];renderCart();toast('Kòmand valide');
}
async function trackOrder(){
  const id=document.getElementById('trackId').value.trim(); if(!id)return;
  const box=document.getElementById('trackResult');
  try{
    const o=await api('/api/orders/'+encodeURIComponent(id));
    box.innerHTML=`<div class="success"><b>${o.code}</b> — <span class="badge ${statusClass(o.status)}">${o.status}</span><br><br>${itemsText(o)}<br><br><b>Total:</b> ${fmt(o.total)}${o.driver?'<br><b>Livreur:</b> '+o.driver:''}</div>`;
  }catch(e){box.innerHTML='<div class="card muted">Nou pa jwenn kòmand sa.</div>'}
}

async function initAdmin(){await reloadAdmin()}
async function reloadAdmin(){
  products=await api('/api/products');orders=await api('/api/orders');const st=await api('/api/stats');const ds=await api('/api/driver-stats');
  document.getElementById('sNew').textContent=st.Nouveau?.count||0;document.getElementById('sPrep').textContent=st['Préparation']?.count||0;
  document.getElementById('sRoute').textContent=st['En route']?.count||0;document.getElementById('sDone').textContent=st['Livré']?.count||0;
  document.getElementById('sRevenue').textContent=fmt(st.revenue_delivered||0);renderAdminProducts();renderOrders();renderDriverStats(ds);
}
function renderDriverStats(ds){
  const box=document.getElementById('driverStats'); if(!box)return;
  box.innerHTML=ds.map(d=>`<div class="driverStatCard"><strong>${d.driver}</strong><span>${d.count} livrezon</span><b>${fmt(d.total)}</b></div>`).join('');
}
function renderAdminProducts(){
  document.getElementById('productManager').innerHTML=products.map(p=>`
    <div class="productEditRow">
      <div class="editIcon">${p.icon}</div>
      <div class="editFields">
        <input id="pn-${p.id}" value="${String(p.name).replace(/"/g,'&quot;')}" aria-label="Non pwodwi">
        <input id="pp-${p.id}" type="number" min="0" value="${Number(p.price||0)}" aria-label="Pri">
      </div>
      <div class="editActions">
        <button class="saveBtn" onclick="saveProduct(${p.id})">💾 Sove</button>
        <button class="removeBtn" onclick="delProduct(${p.id})">Retire</button>
      </div>
    </div>`).join('');
}

async function saveProduct(id){
  const name=document.getElementById('pn-'+id).value.trim();
  const price=Number(document.getElementById('pp-'+id).value||0);
  if(!name)return alert('Mete non pwodwi a.');
  await api('/api/products/'+id,{
    method:'PUT',
    body:JSON.stringify({name,price})
  });
  await reloadAdmin();
  toast('✅ Pwodwi ak pri mete ajou');
}

async function addProduct(){
  const name=document.getElementById('pname').value.trim();if(!name)return alert('Mete non pwodwi a');
  await api('/api/products',{method:'POST',body:JSON.stringify({name,price:Number(document.getElementById('pprice').value||0),category:document.getElementById('pcat').value,icon:document.getElementById('picon').value||'📦'})});
  document.getElementById('pname').value='';document.getElementById('pprice').value='';document.getElementById('picon').value='';await reloadAdmin();toast('Pwodwi ajoute');
}
async function delProduct(id){await api('/api/products/'+id,{method:'DELETE'});await reloadAdmin()}
function renderOrders(){
  document.getElementById('orders').innerHTML=orders.length?orders.map(o=>`<tr>
    <td><b>${o.code}</b><br><small>${o.created_at}</small></td><td><b>${o.customer}</b><br>${o.phone}</td>
    <td>${itemsText(o)}${o.note?'<br><small>📝 '+o.note+'</small>':''}</td><td><b>${fmt(o.total)}</b><br><small>Fee ${fmt(o.delivery_fee)}</small><br><small><b>${o.payment}</b>${o.transaction_id?'<br>Tx: '+o.transaction_id:''}${o.payment!=='Cash'?'<br>'+o.payment_status:''}</small></td>
    <td>${o.address}${o.landmark?'<br><small>📌 '+o.landmark+'</small>':''}</td>
    <td><span class="badge ${statusClass(o.status)}">${o.status}</span><br><select onchange="patchOrder(${o.id},'status',this.value)">${['Nouveau','Préparation','En route','Livré','Annulé'].map(s=>`<option ${s===o.status?'selected':''}>${s}</option>`).join('')}</select></td>
    <td><select onchange="patchOrder(${o.id},'driver',this.value)"><option value="">Non assigné</option>${['Jeff','Duckens','Jn Fritz'].map(d=>`<option ${d===o.driver?'selected':''}>${d}</option>`).join('')}</select></td>
    <td>${o.payment!=='Cash'?`<button class="saveBtn" onclick="paymentStatus(${o.id},'Konfime')">Konfime</button> <button class="removeBtn" onclick="paymentStatus(${o.id},'Refize')">Refize</button><br><br>`:''}<button onclick="copyOrderSummaryById(${o.id})">📋 Mesaj</button> <button onclick="deleteOrder(${o.id})">Efase</button></td></tr>`).join(''):'<tr><td colspan="8">Pa gen kòmand.</td></tr>';
}
async function patchOrder(id,key,val){await api('/api/orders/'+id,{method:'PATCH',body:JSON.stringify({[key]:val})});await reloadAdmin();toast('Mete ajou')}
async function paymentStatus(id,status){await api('/api/orders/'+id,{method:'PATCH',body:JSON.stringify({payment_status:status})});await reloadAdmin();toast('Peman '+status.toLowerCase())}
async function deleteOrder(id){if(confirm('Efase kòmand sa?')){await api('/api/orders/'+id,{method:'DELETE'});await reloadAdmin()}}

async function initDriver(){await loadDriver()}
async function loadDriver(){
  orders=await api('/api/driver/orders');
  document.getElementById('driverOrders').innerHTML=orders.length?orders.map(o=>`<div class="driverCard"><h3>${o.code} <span class="badge ${statusClass(o.status)}">${o.status}</span></h3>
    <p><b>${o.customer}</b> — ${o.phone}</p><p>${o.address}${o.landmark?' — '+o.landmark:''}</p><p>${itemsText(o)}</p><p><b>${fmt(o.total)}</b> — ${o.payment}</p>
    <button onclick="driverStatus(${o.id},'En route')">🛵 Sou wout</button> <button onclick="driverStatus(${o.id},'Livré')">✅ Livré</button></div>`).join(''):'<div class="card muted">Pa gen kòmand aktif pou ou.</div>';
}
async function driverStatus(id,status){await api('/api/orders/'+id,{method:'PATCH',body:JSON.stringify({status})});await loadDriver();toast('Estati mete ajou')}

function copyOrderSummaryById(id){
  const o=orders.find(x=>x.id===id);
  if(!o)return;
  const txt=`PROMO DELIVERY
Kòmand: ${o.code}
Kliyan: ${o.customer}
Telefòn: ${o.phone}
Adrès: ${o.address}${o.landmark?' - '+o.landmark:''}
Atik: ${o.items.map(i=>i.name+' x'+i.qty).join(', ')}
Total: ${fmt(o.total)}
Peman: ${o.payment}${o.transaction_id?' / Tx: '+o.transaction_id:''}${o.payment!=='Cash'?' / '+o.payment_status:''}
Estati: ${o.status}`;
  if(navigator.clipboard){
    navigator.clipboard.writeText(txt).then(()=>toast('Mesaj kòmand lan kopye'));
  }else{
    prompt('Kopye mesaj sa:',txt);
  }
}

function toggleLoginRole(){
  const role=document.getElementById('loginRole'), user=document.getElementById('loginUser');
  if(!role||!user)return;
  if(role.value==='driver'){user.placeholder='Jeff / Duckens / Jn Fritz';}else{user.placeholder='admin';}
}
