const state = {
  data: null,
  lang: localStorage.getItem('jb_lang') || 'en',
  category: 'all',
  visual: 'all',
  query: '',
  cart: JSON.parse(localStorage.getItem('jb_cart_v4') || '[]'),
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const money = value => value == null ? 'Quote' : `$${Number(value).toFixed(2)}`;
const esc = s => String(s ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
const currentName = item => state.lang === 'es' ? item.name_es : item.name_en;
const currentDescription = item => state.lang === 'es' ? item.description_es : item.description_en;

const copy = {
  en: {
    nav_menu:'Menu', nav_wholesale:'Wholesale', nav_quotes:'Cakes & seasonal', nav_partners:'Partners', nav_admin:'Admin', account:'Account',
    eyebrow:'Oaxacan breads • cakes • wholesale orders', hero_title:'Order Mexican bread without guessing what is available.', hero_text:'Browse by the way the bread looks, see real pickup windows, submit cake quotes, and create recurring shop orders.', shop_now:'Shop the case', request_quote:'Request a quote',
    pain_1_title:'Find bread visually', pain_1:'Spanish and English names, aliases, shapes, and fillings.', pain_2_title:'Avoid bad pickups', pain_2:'Hours, capacity, inventory, and lead times are checked before ordering.', pain_3_title:'Wholesale built in', pain_3:'Premium pricing, applications, standing orders, and bulk bundles.', pain_4_title:'Quotes are real workflows', pain_4:'Cakes, Rosca, and Pan de Muerto collect the details staff need.',
    find_bread:'Find your bread', bulk_friendly:'Bulk friendly only', orderable_now:'Orderable now only', search_note:'Search accepts English, Spanish, visual words, and common misspellings.', catalog_eyebrow:'Expanded catalog', catalog_title:'Specific products, variants, and quote-only items', catalog_copy:'Prices use the public menu where available. Items with variable decoration or seasonal sizing use quote requests.',
    quote_eyebrow:'Cakes and seasonal bread', quote_title:'Quote forms collect the missing details before staff call back.', quote_copy:'Custom cakes, Pan de Muerto, and Rosca de Reyes need sizes, fillings, decoration notes, event dates, and pickup timing.', start_quote:'Start quote request', cake_quote:'Custom cakes', cake_quote_desc:'Flavor, filling, inscription, reference image, budget, event date.', rosca_quote_desc:'Size, quantity, pickup window, hidden figurine planning.', muerto_quote_desc:'White sugar, pink sugar, or Oaxacan yema face style.',
    wholesale_eyebrow:'Premium customer flow', wholesale_title:'For shops that buy bread every week', wholesale_copy:'Apply for premium pricing, save standing orders, and reorder bulk bread without rebuilding the basket.', apply_wholesale:'Apply for wholesale', submit_application:'Submit application', standing_orders:'Standing orders', standing_copy:'Approved premium accounts can save recurring orders such as “60 bolillos every Friday at 7:30 AM.”',
    partners_eyebrow:'Community shelf', partners_title:'Businesses buying from the bakery can be promoted here.', partners_copy:'The app requires consent before publishing real partner cards. Demo cards remain marked until replaced.', basket:'Basket', promo_code:'Promo code', subtotal:'Subtotal', checkout:'Checkout', login:'Login', register:'Register', login_title:'Login', login_note:'Demo credentials are in the README. Passwords are intentionally not prefilled.', register_title:'Create customer account', create_account:'Create account', checkout_title:'Pickup checkout', contact_info:'Contact', pickup_info:'Pickup', pay_pickup:'Pay at pickup', deposit_pending:'Deposit to be collected', place_order:'Place pickup order', quote_dialog_title:'Quote request', quote_item:'Item', details:'Details', submit_quote:'Submit quote request'
  },
  es: {
    nav_menu:'Menú', nav_wholesale:'Mayoreo', nav_quotes:'Pasteles y temporada', nav_partners:'Negocios', nav_admin:'Admin', account:'Cuenta',
    eyebrow:'Panes oaxaqueños • pasteles • mayoreo', hero_title:'Ordena pan mexicano sin adivinar qué está disponible.', hero_text:'Busca por cómo se ve el pan, revisa horarios reales, pide cotizaciones y guarda pedidos recurrentes para negocios.', shop_now:'Ver vitrina', request_quote:'Pedir cotización',
    pain_1_title:'Encuentra por forma', pain_1:'Nombres en español e inglés, alias, formas y rellenos.', pain_2_title:'Evita malos horarios', pain_2:'El sistema revisa horario, cupo, inventario y anticipación.', pain_3_title:'Mayoreo incluido', pain_3:'Precios premium, solicitudes, pedidos fijos y paquetes grandes.', pain_4_title:'Cotizaciones útiles', pain_4:'Pasteles, Rosca y Pan de Muerto capturan los datos que necesita el personal.',
    find_bread:'Busca tu pan', bulk_friendly:'Solo mayoreo', orderable_now:'Solo disponible para ordenar', search_note:'La búsqueda acepta español, inglés, palabras visuales y errores comunes.', catalog_eyebrow:'Catálogo ampliado', catalog_title:'Productos específicos, variantes y artículos con cotización', catalog_copy:'Los precios usan el menú público cuando está disponible. Decoración variable y temporada usan cotización.',
    quote_eyebrow:'Pasteles y pan de temporada', quote_title:'Las cotizaciones reúnen los datos antes de llamar al cliente.', quote_copy:'Pasteles personalizados, Pan de Muerto y Rosca de Reyes necesitan tamaños, rellenos, decoración, fecha y hora.', start_quote:'Iniciar cotización', cake_quote:'Pasteles personalizados', cake_quote_desc:'Sabor, relleno, letrero, imagen de referencia, presupuesto y fecha.', rosca_quote_desc:'Tamaño, cantidad, horario y planeación de figuras.', muerto_quote_desc:'Azúcar blanca, azúcar rosa o pan de yema oaxaqueño con carita.',
    wholesale_eyebrow:'Flujo premium', wholesale_title:'Para negocios que compran pan cada semana', wholesale_copy:'Solicita precio premium, guarda pedidos fijos y repite pedidos grandes sin rehacer la canasta.', apply_wholesale:'Solicitar mayoreo', submit_application:'Enviar solicitud', standing_orders:'Pedidos fijos', standing_copy:'Cuentas premium pueden guardar pedidos como “60 bolillos cada viernes a las 7:30 AM.”',
    partners_eyebrow:'Comunidad', partners_title:'Los negocios que compran de la panadería se pueden promover aquí.', partners_copy:'La app exige consentimiento antes de publicar negocios reales. Las tarjetas demo quedan marcadas.', basket:'Canasta', promo_code:'Código promo', subtotal:'Subtotal', checkout:'Pagar', login:'Entrar', register:'Registro', login_title:'Entrar', login_note:'Las credenciales demo están en README. Las contraseñas no se autollenan.', register_title:'Crear cuenta', create_account:'Crear cuenta', checkout_title:'Pedido para recoger', contact_info:'Contacto', pickup_info:'Recoger', pay_pickup:'Pagar al recoger', deposit_pending:'Depósito pendiente', place_order:'Enviar pedido', quote_dialog_title:'Solicitud de cotización', quote_item:'Artículo', details:'Detalles', submit_quote:'Enviar cotización'
  }
};

function t(key){ return (copy[state.lang] && copy[state.lang][key]) || copy.en[key] || key; }
function normalize(text){ return String(text || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9\s-]/g,' '); }
function saveCart(){ localStorage.setItem('jb_cart_v4', JSON.stringify(state.cart)); renderCart(); }
async function api(path, options = {}){
  const headers = {'Content-Type':'application/json'};
  if(state.data?.user?.csrf_token) headers['X-CSRF-Token'] = state.data.user.csrf_token;
  const res = await fetch(path, {headers, credentials:'same-origin', ...options});
  const json = await res.json().catch(() => ({}));
  if(!res.ok || json.ok === false) throw new Error(json.error || `Request failed: ${res.status}`);
  return json;
}

async function boot(){
  state.data = await api('/api/bootstrap');
  applyLanguage();
  renderStatus();
  renderCategories();
  renderVisualChips();
  renderPromos();
  renderBundles();
  renderBakeryCase();
  renderCampaignCapacity();
  renderProducts();
  renderPartners();
  renderCart();
  renderAccount();
  renderQuoteProducts();
  renderReviewProducts();
  renderStandingOutside();
  renderCampaigns();
  bindEvents();
}

function applyLanguage(){
  document.documentElement.lang = state.lang;
  $$('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
  $('#languageBtn').textContent = state.lang === 'en' ? 'Español' : 'English';
  renderProducts(); renderCart(); renderPartners(); renderStatus(); renderAccount(); renderQuoteProducts(); renderReviewProducts(); renderCampaigns(); renderVisualChips(); renderBakeryCase(); renderCampaignCapacity();
}

function renderStatus(){
  const s = state.data?.store_status;
  if(!s) return;
  const label = state.lang === 'es' ? s.message_es : s.message_en;
  $('#storeStatus').innerHTML = `<span class="status-dot ${s.is_open ? '' : 'closed'}"></span><div><strong>${label}</strong><br><small>${state.lang === 'es' ? s.day_es : s.day_en}: ${s.opens_at || '—'}–${s.closes_at || '—'}</small></div>`;
}

function renderCategories(){
  const wrap = $('#categoryChips');
  const cats = [{key:'all', name_en:'All products', name_es:'Todo'}, ...state.data.categories];
  wrap.innerHTML = cats.map(cat => `<button class="chip ${state.category === cat.key ? 'active' : ''}" data-category="${cat.key}" type="button">${state.lang === 'es' ? cat.name_es : cat.name_en}</button>`).join('');
  $$('.chip', wrap).forEach(btn => btn.addEventListener('click', () => { state.category = btn.dataset.category; renderCategories(); renderProducts(); }));
}

function renderVisualChips(){
  const wrap = $('#visualChips'); if(!wrap || !state.data) return;
  const labels = {all:'All shapes', shell:'Shells', pig:'Pigs', heart:'Hearts', ring:'Rings', filled:'Filled', flaky:'Flaky', cookie:'Cookies', slice:'Slices', cake:'Cakes', roll:'Rolls', other:'Other'};
  const labelsEs = {all:'Todas', shell:'Conchas', pig:'Marranitos', heart:'Corazones', ring:'Roscas/aretes', filled:'Rellenos', flaky:'Hojaldres', cookie:'Galletas', slice:'Rebanadas', cake:'Pasteles', roll:'Bolillos', other:'Otros'};
  const shapes = ['all', ...(state.data.visual_shapes || []).map(v => v.visual_shape || 'other')];
  const unique = [...new Set(shapes)].filter(Boolean);
  wrap.innerHTML = unique.map(shape => `<button class="chip ${state.visual === shape ? 'active' : ''}" data-visual="${esc(shape)}" type="button">${state.lang === 'es' ? (labelsEs[shape] || shape) : (labels[shape] || shape)}</button>`).join('');
  $$('[data-visual]', wrap).forEach(btn => btn.addEventListener('click', () => { state.visual = btn.dataset.visual; renderVisualChips(); renderProducts(); }));
}

function renderBakeryCase(){
  const rail = $('#bakeryCaseRail'); if(!rail || !state.data) return;
  const batches = state.data.product_batches || [];
  rail.innerHTML = batches.slice(0,8).map(b => `<article class="case-batch ${b.status}"><b>${esc(b.name_es)}</b><small>${esc(b.batch_label)} • ${esc(b.batch_date)} ${esc(b.expected_ready_at)} • ${esc(b.status)}</small><span>${Number(b.produced_qty || 0) - Number(b.reserved_qty || 0) - Number(b.sold_qty || 0)} planned left</span></article>`).join('') || `<div class="empty-state">Bakery case batch planning is not configured yet.</div>`;
}

function renderCampaignCapacity(){
  const box = $('#campaignCapacity'); if(!box || !state.data) return;
  const campaigns = state.data.seasonal_campaigns || [];
  box.innerHTML = campaigns.map(c => {
    const max = Number(c.max_orders || 0); const reserved = Number(c.current_reserved || 0); const pct = max ? Math.min(100, Math.round((reserved/max)*100)) : 0;
    return `<article class="capacity-card"><div><b>${state.lang === 'es' ? esc(c.title_es) : esc(c.title_en)}</b><small>${esc(c.season_start)} → ${esc(c.season_end)} • cutoff ${esc(c.preorder_cutoff)}</small></div><div class="capacity-meter"><span style="width:${pct}%"></span></div><small>${reserved}/${max || '∞'} reserved • ${esc(c.status)}</small></article>`;
  }).join('');
}

function renderPromos(){
  const rail = $('#promoRail');
  const promos = state.data.promotions || [];
  rail.innerHTML = promos.slice(0,3).map(p => `<article class="promo-card"><b>${p.title}</b><small>${p.code} • ${p.discount_type === 'percent' ? `${p.discount_value}%` : money(p.discount_value)} off • min ${money(p.min_subtotal)}</small></article>`).join('');
}

function renderBundles(){
  const rail = $('#bundleRail');
  rail.innerHTML = (state.data.bundles || []).map(b => `<article class="bundle-card"><b>${state.lang === 'es' ? b.name_es : b.name_en}</b><small>${state.lang === 'es' ? b.description_es : b.description_en}</small><button data-bundle="${b.slug}" type="button">${state.lang === 'es' ? 'Agregar paquete' : 'Add bundle'}</button></article>`).join('');
  $$('[data-bundle]', rail).forEach(btn => btn.addEventListener('click', () => addBundle(btn.dataset.bundle)));
}

function productSearchBlob(p){
  return normalize([p.name_es,p.name_en,p.description_es,p.description_en,p.search_terms,p.visual_tags,p.visual_shape,p.category_name_en,p.category_name_es,p.subcategory].join(' '));
}

function filteredProducts(){
  const q = normalize(state.query);
  return state.data.products.filter(p => {
    if(state.category !== 'all' && p.category_key !== state.category) return false;
    if(state.visual !== 'all' && (p.visual_shape || 'other') !== state.visual) return false;
    if($('#bulkOnly')?.checked && !p.is_bulk_friendly) return false;
    if($('#orderableOnly')?.checked && !p.can_order) return false;
    if(q && !productSearchBlob(p).includes(q)) return false;
    return true;
  });
}

function groupVariants(variants){
  return variants.reduce((acc, v) => { (acc[v.variant_type] ||= []).push(v); return acc; }, {});
}

function productPhotoAlt(p){
  if(p.image_alt) return p.image_alt;
  if(p.product_image_status === 'needsOwnerPhoto') return `Photo coming soon for ${p.name_en}.`;
  return `${p.name_es} / ${p.name_en}`;
}

function productArtHtml(extraClass = ''){
  return `<div class="product-art ${extraClass}"><img class="product-photo" alt="" loading="lazy" decoding="async"><div class="photo-coming-soon" role="img" aria-label="" hidden><img src="/imported/website/010-juquilita-bakery-logo.png" alt="" aria-hidden="true"><b>Photo coming soon</b></div></div>`;
}

function setProductArt(art, p){
  const img = $('.product-photo', art);
  const comingSoon = $('.photo-coming-soon', art);
  const logo = $('.photo-coming-soon img', art);
  const alt = productPhotoAlt(p);
  art.classList.toggle('needs-owner-photo', !p.image_url);
  if(p.image_url){
    img.hidden = false;
    img.src = p.image_url;
    img.alt = alt;
    comingSoon.hidden = true;
    comingSoon.setAttribute('aria-label', '');
  } else {
    img.hidden = true;
    img.removeAttribute('src');
    img.alt = '';
    if(logo && p.photo_placeholder_url) logo.src = p.photo_placeholder_url;
    comingSoon.hidden = false;
    comingSoon.setAttribute('aria-label', alt);
  }
}

function renderProducts(){
  if(!state.data) return;
  const grid = $('#productGrid');
  const tpl = $('#productTemplate');
  const products = filteredProducts();
  $('#productCount').textContent = `${products.length}`;
  if(!products.length){ grid.innerHTML = `<div class="empty-state">${state.lang === 'es' ? 'No se encontraron productos.' : 'No products found.'}</div>`; return; }
  grid.innerHTML = '';
  for(const p of products){
    const node = tpl.content.firstElementChild.cloneNode(true);
    const art = $('.product-art', node);
    setProductArt(art, p);
    $('.category-badge', node).textContent = state.lang === 'es' ? p.category_name_es : p.category_name_en;
    const stock = $('.stock-badge', node);
    if(p.order_mode === 'quote'){ stock.textContent = state.lang === 'es' ? 'cotización' : 'quote'; stock.classList.add('quote'); }
    else if(p.stock_policy === 'track'){ stock.textContent = p.stock_count < 20 ? `${p.stock_count} left` : 'daily case'; if(p.stock_count < 20) stock.classList.add('low'); }
    else { stock.textContent = state.lang === 'es' ? 'por pedido' : 'made to order'; }
    $('h3', node).textContent = `${p.name_es} / ${p.name_en}`;
    $('p', node).textContent = currentDescription(p);
    const variantBox = $('.variant-box', node);
    const groups = groupVariants(p.variants || []);
    variantBox.innerHTML = Object.entries(groups).map(([type, variants]) => `<select data-variant-type="${type}"><option value="">${type.replace('_',' ')}</option>${variants.map(v => `<option value="${v.id}" ${v.is_default ? 'selected' : ''}>${state.lang === 'es' ? v.name_es : v.name_en}${Number(v.price_delta) ? ` +${money(v.price_delta)}` : ''}</option>`).join('')}</select>`).join('');
    const allergenRow = $('.allergen-row', node);
    allergenRow.innerHTML = (p.allergens || []).slice(0,4).map(a => `<span>${state.lang === 'es' ? a.name_es : a.name_en}</span>`).join('');
    const trust = $('.product-trust', node);
    const verifyLabel = p.verification_status === 'owner_verified' ? 'owner verified' : 'needs owner check';
    trust.innerHTML = `<span>${esc(p.visual_shape || 'case')}</span><span>${esc(verifyLabel)}</span><span>${Number(p.completeness_score || 0)}% complete</span>`;
    const fav = $('.favorite-btn', node);
    fav.textContent = p.is_favorite ? (state.lang === 'es' ? '♥ Guardado' : '♥ Saved') : (state.lang === 'es' ? '♡ Guardar' : '♡ Save');
    fav.addEventListener('click', () => toggleFavorite(p));
    $('.details-btn', node).addEventListener('click', () => openProductDetails(p));
    $('.price', node).textContent = p.order_mode === 'quote' ? (state.lang === 'es' ? 'Cotizar' : 'Quote') : money(p.effective_price);
    const btn = $('.product-foot button', node);
    btn.textContent = p.order_mode === 'quote' ? (state.lang === 'es' ? 'Cotizar' : 'Quote') : (state.lang === 'es' ? 'Agregar' : 'Add');
    if(p.order_mode === 'quote') btn.classList.add('quote');
    btn.addEventListener('click', () => p.order_mode === 'quote' ? openQuote(p.slug) : addProductFromCard(p, node));
    const imageStatusLabel = {
      legacyVerified: state.lang === 'es' ? 'Foto real verificada' : 'Verified real photo',
      categoryFallback: state.lang === 'es' ? 'Foto de categoría' : 'Category photo',
      needsOwnerPhoto: state.lang === 'es' ? 'Foto pendiente' : 'Photo coming soon'
    }[p.product_image_status] || (state.lang === 'es' ? 'Foto pendiente' : 'Photo coming soon');
    $('.source-line', node).textContent = `${imageStatusLabel} • ${p.price_basis}`;
    grid.appendChild(node);
  }
}

function selectedVariants(card){
  return $$('select[data-variant-type]', card).map(sel => Number(sel.value)).filter(Boolean);
}
function variantLabel(product, ids){
  const labels = [];
  for(const id of ids){ const v = product.variants.find(x => Number(x.id) === Number(id)); if(v) labels.push(`${v.variant_type}: ${state.lang === 'es' ? v.name_es : v.name_en}`); }
  return labels.join('; ');
}
function variantDelta(product, ids){
  return ids.reduce((sum,id) => { const v = product.variants.find(x => Number(x.id) === Number(id)); return sum + (v ? Number(v.price_delta || 0) : 0); }, 0);
}
function addProductFromCard(product, card){ addToCart(product.slug, 1, selectedVariants(card)); }
function cartKey(slug, variantIds){ return `${slug}|${[...variantIds].sort((a,b)=>a-b).join(',')}`; }
function addToCart(slug, qty = 1, variantIds = []){
  const p = state.data.products.find(x => x.slug === slug); if(!p) return;
  const key = cartKey(slug, variantIds);
  const existing = state.cart.find(item => item.key === key);
  if(existing) existing.quantity += qty; else state.cart.push({key, slug, quantity: qty, variant_ids: variantIds, variant_label: variantLabel(p, variantIds)});
  saveCart(); openCart();
}
function addBundle(slug){
  const b = state.data.bundles.find(x => x.slug === slug); if(!b) return;
  const items = JSON.parse(b.items_json || '{}');
  Object.entries(items).forEach(([productSlug, qty]) => addToCart(productSlug, Number(qty), []));
}
function renderCart(){
  const count = state.cart.reduce((s,i)=>s+i.quantity,0);
  $('#cartCount').textContent = count;
  const wrap = $('#cartItems');
  if(!state.cart.length){ wrap.innerHTML = `<div class="empty-state">${state.lang === 'es' ? 'Tu canasta está vacía.' : 'Your basket is empty.'}</div>`; $('#cartSubtotal').textContent = money(0); return; }
  let subtotal = 0;
  wrap.innerHTML = state.cart.map((item, idx) => {
    const p = state.data.products.find(x => x.slug === item.slug);
    if(!p) return '';
    const unit = Number(p.effective_price || p.base_price || 0) + variantDelta(p, item.variant_ids || []);
    subtotal += unit * item.quantity;
    return `<article class="cart-line"><div class="cart-line-top"><div><strong>${p.name_es}</strong><br><small>${p.name_en}${item.variant_label ? ' • ' + item.variant_label : ''}</small></div><b>${money(unit * item.quantity)}</b></div><div class="qty-row"><button data-dec="${idx}">−</button><span>${item.quantity}</span><button data-inc="${idx}">+</button><button data-remove="${idx}">${state.lang === 'es' ? 'quitar' : 'remove'}</button></div></article>`;
  }).join('');
  $('#cartSubtotal').textContent = money(subtotal);
  $$('[data-inc]', wrap).forEach(b => b.addEventListener('click', () => { state.cart[Number(b.dataset.inc)].quantity++; saveCart(); }));
  $$('[data-dec]', wrap).forEach(b => b.addEventListener('click', () => { const i = state.cart[Number(b.dataset.dec)]; i.quantity--; if(i.quantity <= 0) state.cart.splice(Number(b.dataset.dec),1); saveCart(); }));
  $$('[data-remove]', wrap).forEach(b => b.addEventListener('click', () => { state.cart.splice(Number(b.dataset.remove),1); saveCart(); }));
}
function openCart(){ $('#cartDrawer').classList.add('open'); $('#drawerShade').classList.add('open'); $('#cartDrawer').setAttribute('aria-hidden','false'); }
function closeCart(){ $('#cartDrawer').classList.remove('open'); $('#drawerShade').classList.remove('open'); $('#cartDrawer').setAttribute('aria-hidden','true'); }

function renderPartners(){
  const wrap = $('#partnerGrid');
  wrap.innerHTML = (state.data.partners || []).map(p => `<article class="partner-card"><span class="demo">${p.is_demo ? (state.lang === 'es' ? 'Demo, reemplazar' : 'Demo, replace') : (p.has_consent ? 'Approved' : 'Needs consent')}</span><h3>${p.name}</h3><b>${p.highlight}</b><p>${p.story}</p><small>${p.category} • ${p.city} • ${p.monthly_volume_estimate || 0} units/mo est.</small></article>`).join('');
}
function renderAccount(){
  const panel = $('#accountPanel'); if(!panel || !state.data) return;
  const u = state.data.user;
  if(!u){ panel.innerHTML = `<div class="account-card">${state.lang === 'es' ? 'No has iniciado sesión.' : 'You are not logged in.'}</div>`; return; }
  const points = state.data.loyalty_summary?.points || 0;
  const orders = (state.data.order_history || []).map(o => `<li><b>${o.order_code}</b> • ${o.pickup_date} ${o.pickup_time} • ${money(o.total)} • ${o.status} • <a href="/receipt?code=${encodeURIComponent(o.order_code)}" target="_blank">receipt</a> <button class="small-inline" data-reorder="${o.id}" type="button">reorder</button> <button class="small-inline" data-change-order="${o.order_code}" data-change-email="${o.customer_email}" type="button">change</button></li>`).join('') || `<li>${state.lang === 'es' ? 'Sin pedidos todavía.' : 'No orders yet.'}</li>`;
  const changes = (state.data.change_requests || []).map(r => `<li><b>${r.order_code}</b> • ${r.request_type} • ${r.status}<br><small>${r.reason}</small></li>`).join('') || `<li>${state.lang === 'es' ? 'Sin solicitudes.' : 'No change requests.'}</li>`;
  const standing = (state.data.standing_orders || []).map(s => `<article><b>${s.name}</b><br><small>${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][s.weekday]} ${s.pickup_time} • ${s.items.length} item(s)</small></article>`).join('') || `<p class="mini-note">${state.lang === 'es' ? 'Sin pedidos fijos.' : 'No standing orders saved.'}</p>`;
  panel.innerHTML = `<div class="account-card"><b>${u.name}</b><br><small>${u.email} • ${u.role}${u.business_name ? ' • ' + u.business_name : ''}</small><br><b>${points}</b> loyalty points<br><button id="logoutBtn" class="secondary-action" type="button" style="margin-top:12px">${state.lang === 'es' ? 'Salir' : 'Logout'}</button></div><h3>${state.lang === 'es' ? 'Pedidos recientes' : 'Recent orders'}</h3><ul>${orders}</ul><h3>Change requests</h3><ul>${changes}</ul><h3>${state.lang === 'es' ? 'Pedidos fijos' : 'Standing orders'}</h3><div class="standing-list">${standing}</div>`;
  $('#logoutBtn')?.addEventListener('click', logout);
  $$('[data-reorder]', panel).forEach(btn => btn.addEventListener('click', () => reorderOrder(btn.dataset.reorder)));
  $$('[data-change-order]', panel).forEach(btn => btn.addEventListener('click', () => fillChangeRequest(btn.dataset.changeOrder, btn.dataset.changeEmail)));
  $('#accountBtn').textContent = u.role === 'premium' ? 'Premium' : (state.lang === 'es' ? 'Cuenta' : 'Account');
}
function renderStandingOutside(){
  const el = $('#standingOrders'); if(!el || !state.data) return;
  const u = state.data.user;
  const form = $('#standingOrderForm');
  if(!u || u.role !== 'premium'){ el.innerHTML = `<p class="mini-note">${state.lang === 'es' ? 'Inicia sesión como cuenta premium para ver pedidos fijos.' : 'Login as a premium account to view and create standing orders.'}</p>`; if(form) form.style.display = 'none'; return; }
  if(form) form.style.display = '';
  const rows = (state.data.standing_orders || []).map(s => `<article><b>${s.name}</b><br><small>${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][s.weekday]} ${s.pickup_time} • ${(s.items||[]).map(i=>`${i.quantity}× ${i.name_es}`).join(', ')} • ${s.is_active ? 'active' : 'paused'}</small></article>`).join('');
  el.innerHTML = rows || `<p class="mini-note">${state.lang === 'es' ? 'Sin pedidos fijos.' : 'No standing orders saved.'}</p>`;
}
function renderQuoteProducts(){
  const select = $('#quoteProduct'); if(!select || !state.data) return;
  const products = state.data.products.filter(p => p.order_mode === 'quote' || p.category_key === 'cakes' || p.category_key === 'seasonal');
  select.innerHTML = `<option value="">${state.lang === 'es' ? 'Selecciona un producto' : 'Select item'}</option>` + products.map(p => `<option value="${p.slug}">${p.name_es} / ${p.name_en}</option>`).join('');
}
function openQuote(slug=''){ renderQuoteProducts(); $('#quoteProduct').value = slug; $('#quoteDialog').showModal(); }

function renderReviewProducts(){
  const select = $('#reviewProduct'); if(!select || !state.data) return;
  const orderable = state.data.products.filter(p => p.order_mode === 'order');
  select.innerHTML = `<option value="">${state.lang === 'es' ? 'Producto, opcional' : 'Product, optional'}</option>` + orderable.slice(0,220).map(p => `<option value="${p.slug}">${p.name_es} / ${p.name_en}</option>`).join('');
}

function renderCampaigns(){
  const pages = $('#seoPagesGrid');
  if(pages){
    pages.innerHTML = (state.data.seo_pages || []).map(p => `<a class="campaign-card" href="/page/${encodeURIComponent(p.slug)}"><b>${esc(p.title)}</b><small>${esc(p.meta_description)}</small><span>${esc(p.target_keyword)}</span></a>`).join('') || `<div class="empty-state">No pages published yet.</div>`;
  }
  const reviews = $('#reviewsGrid');
  if(reviews){
    reviews.innerHTML = (state.data.reviews || []).slice(0,6).map(r => `<article class="review-card"><b>${'★'.repeat(Number(r.rating))}</b><strong>${esc(r.title || r.name_es || 'Review')}</strong><p>${esc(r.body)}</p><small>${esc(r.customer_name)}</small></article>`).join('') || `<div class="empty-state">No approved reviews yet.</div>`;
  }
  const zones = $('#deliveryZones');
  if(zones){
    zones.innerHTML = (state.data.delivery_zones || []).map(z => `<article class="delivery-card"><b>${esc(z.name)}</b><span>${esc(z.status)}</span><small>${esc(z.city)} • min ${money(z.min_order)} • fee ${money(z.fee)}</small><p>${esc(z.notes)}</p></article>`).join('');
  }
}

async function toggleFavorite(product){
  if(!state.data.user){ $('#accountDialog').showModal(); return; }
  try{
    await api('/api/account/favorite', {method:'POST', body:JSON.stringify({slug:product.slug, enabled:!product.is_favorite})});
    state.data = await api('/api/bootstrap');
    renderProducts(); renderAccount();
  }catch(err){ alert(err.message); }
}

function openProductDetails(p){
  const allergens = (p.allergens || []).map(a => `<span>${state.lang === 'es' ? a.name_es : a.name_en}</span>`).join('') || '<span>Ask staff</span>';
  const variants = Object.entries(groupVariants(p.variants || [])).map(([type, variants]) => `<li><b>${type}</b>: ${variants.map(v => `${state.lang === 'es' ? v.name_es : v.name_en}${Number(v.price_delta) ? ` +${money(v.price_delta)}` : ''}`).join(', ')}</li>`).join('') || '<li>No selectable variants.</li>';
  $('#productDetails').innerHTML = `<div class="detail-layout">${productArtHtml('large')}<div><p class="eyebrow">${p.category_name_en} • ${esc(p.visual_shape || 'case')}</p><h2>${p.name_es} / ${p.name_en}</h2><p>${currentDescription(p)}</p><p><b>${p.order_mode === 'quote' ? 'Quote required' : money(p.effective_price)}</b> • ${p.price_label}</p><div class="product-trust detail"><span>${esc(p.verification_status || 'unverified')}</span><span>${Number(p.completeness_score || 0)}% complete</span><span>${esc(p.product_image_status || 'needsOwnerPhoto')}</span></div><h3>Options</h3><ul>${variants}</ul><h3>Allergens</h3><div class="allergen-row">${allergens}</div><h3>Source and operations</h3><p class="mini-note">${p.price_basis || ''}<br>Lead time: ${p.lead_time_hours || 0} hours • Stock policy: ${p.stock_policy}<br>Visual tags: ${esc(p.visual_tags || '')}<br>Image key: ${esc(p.canonical_key || '')}</p></div></div>`;
  setProductArt($('.product-art.large'), p);
  $('#productDialog').showModal();
}

async function reorderOrder(orderId){
  try{
    const res = await api('/api/account/reorder', {method:'POST', body:JSON.stringify({order_id:orderId})});
    for(const item of res.items){ addToCart(item.slug, item.quantity, item.variant_ids || []); }
    $('#accountDialog').close();
    openCart();
  }catch(err){ alert(err.message); }
}

function fillChangeRequest(code, email){
  const form = $('#orderChangeForm');
  form.order_code.value = code || '';
  form.email.value = email || '';
  location.hash = '#selfservice';
  $('#accountDialog').close();
}

async function submitOrderChange(form){
  const msg = $('#orderChangeMessage'); msg.className='form-message'; msg.textContent='';
  try{ const data=Object.fromEntries(new FormData(form).entries()); const res=await api('/api/account/order-change-request',{method:'POST', body:JSON.stringify(data)}); msg.textContent=`Request #${res.request_id} received.`; form.reset(); state.data=await api('/api/bootstrap'); renderAccount(); }
  catch(err){ msg.className='form-message error'; msg.textContent=err.message; }
}

async function submitReview(form){
  const msg = $('#reviewMessage'); msg.className='form-message'; msg.textContent='';
  try{ const data=Object.fromEntries(new FormData(form).entries()); const res=await api('/api/account/review',{method:'POST', body:JSON.stringify(data)}); msg.textContent=`Review #${res.review_id} submitted for approval.`; form.reset(); }
  catch(err){ msg.className='form-message error'; msg.textContent=err.message; }
}

async function resetPassword(form){
  const msg = $('#authMessage'); msg.className='form-message'; msg.textContent='';
  try{ const data=Object.fromEntries(new FormData(form).entries()); await api('/api/account/password-reset',{method:'POST', body:JSON.stringify(data)}); msg.textContent='If that account exists, a reset message was queued in the notification outbox.'; form.reset(); }
  catch(err){ msg.className='form-message error'; msg.textContent=err.message; }
}

function updateCheckoutReview(){
  const lines = state.cart.map(item => {
    const p = state.data.products.find(x => x.slug === item.slug); if(!p) return '';
    const unit = Number(p.effective_price || p.base_price || 0) + variantDelta(p, item.variant_ids || []);
    return `<div class="review-line"><span>${item.quantity} × ${p.name_es}${item.variant_label ? ' • ' + item.variant_label : ''}</span><b>${money(unit * item.quantity)}</b></div>`;
  }).join('');
  $('#checkoutReview').innerHTML = lines || `<div class="empty-state">${state.lang === 'es' ? 'Canasta vacía' : 'Empty basket'}</div>`;
}

async function submitCheckout(form){
  const msg = $('#checkoutMessage'); msg.className = 'form-message'; msg.textContent = '';
  try{
    if(!state.cart.length) throw new Error(state.lang === 'es' ? 'La canasta está vacía.' : 'Basket is empty.');
    const fd = new FormData(form);
    const payload = {
      customer: {name: fd.get('name'), email: fd.get('email'), phone: fd.get('phone'), business_name: fd.get('business_name')},
      pickup_date: fd.get('pickup_date'), pickup_time: fd.get('pickup_time'), payment_method: fd.get('payment_method'), notes: fd.get('notes'), promo_code: $('#promoCode').value,
      customer_language: fd.get('customer_language') || state.lang, substitution_preference: fd.get('substitution_preference') || 'call_me',
      items: state.cart.map(i => ({slug:i.slug, quantity:i.quantity, variant_ids:i.variant_ids || []}))
    };
    const res = await api('/api/checkout', {method:'POST', body:JSON.stringify(payload)});
    const paymentLink = res.payment_intent?.checkout_url ? ` • <a href="${esc(res.payment_intent.checkout_url)}" target="_blank">${state.lang === 'es' ? 'pagar depósito' : 'pay deposit'}</a>` : (res.payment_intent ? ` • payment ${money(res.payment_intent.amount)}` : '');
    msg.innerHTML = `${state.lang === 'es' ? 'Pedido recibido' : 'Order received'}: <b>${res.order_code}</b> • ${money(res.total)}${res.deposit_due ? ` • Deposit ${money(res.deposit_due)}` : ''} • <a href="${res.receipt_url}" target="_blank">receipt</a>${paymentLink}`;
    state.cart = []; saveCart();
    state.data = await api('/api/bootstrap');
    renderProducts(); renderAccount(); renderStandingOutside(); renderCampaigns();
  }catch(err){ msg.className = 'form-message error'; msg.textContent = err.message; }
}
async function submitQuote(form){
  const msg = $('#quoteMessage'); msg.className = 'form-message'; msg.textContent='';
  try{ const data = Object.fromEntries(new FormData(form).entries()); const res = await api('/api/quote', {method:'POST', body:JSON.stringify(data)}); msg.textContent = `${state.lang === 'es' ? 'Cotización recibida' : 'Quote received'}: ${res.quote_code}`; form.reset(); }
  catch(err){ msg.className = 'form-message error'; msg.textContent = err.message; }
}
async function submitWholesale(form){
  const msg = $('#wholesaleMessage'); msg.className = 'form-message'; msg.textContent='';
  try{ const data = Object.fromEntries(new FormData(form).entries()); const res = await api('/api/wholesale/apply', {method:'POST', body:JSON.stringify(data)}); msg.textContent = `${state.lang === 'es' ? 'Solicitud recibida' : 'Application received'}: ${res.status}`; form.reset(); }
  catch(err){ msg.className='form-message error'; msg.textContent=err.message; }
}
async function submitStandingOrder(form){
  const msg = $('#standingOrderMessage'); msg.className='form-message'; msg.textContent='';
  try{ const fd = new FormData(form); const payload = {name:fd.get('name'), weekday:fd.get('weekday'), pickup_time:fd.get('pickup_time'), business_name:fd.get('business_name'), notes:fd.get('notes'), items:[{slug:fd.get('product_slug'), quantity:fd.get('quantity')}]} ; const res = await api('/api/account/standing-orders',{method:'POST', body:JSON.stringify(payload)}); msg.textContent = `Standing order saved #${res.standing_order_id}`; form.reset(); state.data = await api('/api/bootstrap'); renderStandingOutside(); renderAccount(); }catch(err){ msg.className='form-message error'; msg.textContent=err.message; }
}
async function trackOrder(form){
  const out = $('#trackOrderResult'); out.className='form-message'; out.textContent='';
  try{ const fd = new FormData(form); const res = await api(`/api/order/track?code=${encodeURIComponent(fd.get('code'))}&email=${encodeURIComponent(fd.get('email'))}`); const o=res.order; out.innerHTML = `<b>${o.order_code}</b> • ${o.pickup_date} ${o.pickup_time} • ${o.status} • ${money(o.total)} • <a href="${esc(o.receipt_url || '#')}" target="_blank">receipt</a>`; }catch(err){ out.className='form-message error'; out.textContent=err.message; }
}
async function login(form){
  const msg = $('#authMessage'); msg.className='form-message'; msg.textContent='';
  try{ const data = Object.fromEntries(new FormData(form).entries()); const res = await api('/api/auth/login', {method:'POST', body:JSON.stringify(data)}); if(res.requires_2fa){ const code = prompt('Enter your 2FA code'); if(!code) throw new Error('2FA code required.'); await api('/api/auth/2fa/verify', {method:'POST', body:JSON.stringify({challenge_token:res.challenge_token, code})}); } state.data = await api('/api/bootstrap'); renderAccount(); renderProducts(); msg.textContent = state.lang === 'es' ? 'Sesión iniciada.' : 'Logged in.'; }
  catch(err){ msg.className='form-message error'; msg.textContent=err.message; }
}
async function register(form){
  const msg = $('#authMessage'); msg.className='form-message'; msg.textContent='';
  try{ const data = Object.fromEntries(new FormData(form).entries()); await api('/api/auth/register', {method:'POST', body:JSON.stringify(data)}); state.data = await api('/api/bootstrap'); renderAccount(); msg.textContent = state.lang === 'es' ? 'Cuenta creada.' : 'Account created.'; }
  catch(err){ msg.className='form-message error'; msg.textContent=err.message; }
}
async function logout(){ await api('/api/auth/logout', {method:'POST', body:'{}'}); state.data = await api('/api/bootstrap'); renderAccount(); renderProducts(); }

function bindEvents(){
  $('#languageBtn').addEventListener('click', () => { state.lang = state.lang === 'en' ? 'es' : 'en'; localStorage.setItem('jb_lang', state.lang); applyLanguage(); renderCategories(); renderVisualChips(); });
  $('#cartButton').addEventListener('click', openCart); $('#closeCart').addEventListener('click', closeCart); $('#drawerShade').addEventListener('click', closeCart);
  $('#searchInput').addEventListener('input', e => { state.query = e.target.value; renderProducts(); });
  $('#bulkOnly').addEventListener('change', renderProducts); $('#orderableOnly').addEventListener('change', renderProducts);
  $('#checkoutToggle').addEventListener('click', () => { updateCheckoutReview(); fillCheckoutFromUser(); $('#checkoutDialog').showModal(); });
  $('#checkoutForm').addEventListener('submit', e => { e.preventDefault(); submitCheckout(e.currentTarget); });
  $('#quoteForm').addEventListener('submit', e => { e.preventDefault(); submitQuote(e.currentTarget); });
  $('#wholesaleForm').addEventListener('submit', e => { e.preventDefault(); submitWholesale(e.currentTarget); });
  $('#standingOrderForm')?.addEventListener('submit', e => { e.preventDefault(); submitStandingOrder(e.currentTarget); });
  $('#trackOrderForm')?.addEventListener('submit', e => { e.preventDefault(); trackOrder(e.currentTarget); });
  $('#openQuoteHero').addEventListener('click', () => openQuote()); $('#openQuoteSection').addEventListener('click', () => openQuote());
  $('#accountBtn').addEventListener('click', () => $('#accountDialog').showModal());
  $('#loginForm').addEventListener('submit', e => { e.preventDefault(); login(e.currentTarget); });
  $('#registerForm').addEventListener('submit', e => { e.preventDefault(); register(e.currentTarget); });
  $('#resetForm')?.addEventListener('submit', e => { e.preventDefault(); resetPassword(e.currentTarget); });
  $('#orderChangeForm')?.addEventListener('submit', e => { e.preventDefault(); submitOrderChange(e.currentTarget); });
  $('#reviewForm')?.addEventListener('submit', e => { e.preventDefault(); submitReview(e.currentTarget); });
  $$('.tabs button').forEach(btn => btn.addEventListener('click', () => { $$('.tabs button').forEach(b=>b.classList.remove('active')); $$('[data-panel]').forEach(p=>p.classList.remove('active')); btn.classList.add('active'); $(`[data-panel="${btn.dataset.tab}"]`).classList.add('active'); }));
}
function fillCheckoutFromUser(){
  const u = state.data.user; if(!u) return;
  const f = $('#checkoutForm'); f.name.value = u.name || ''; f.email.value = u.email || ''; f.phone.value = u.phone || ''; f.business_name.value = u.business_name || '';
}

boot().catch(err => { console.error(err); document.body.insertAdjacentHTML('afterbegin', `<div class="warning-box">${err.message}</div>`); });
