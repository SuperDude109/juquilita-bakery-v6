const state = {
  data: null,
  lang: localStorage.getItem('jb_lang') || 'en',
  category: 'all',
  visual: 'all',
  price: 'all',
  sort: 'popular',
  query: '',
  expandedSections: {},
  cart: JSON.parse(localStorage.getItem('jb_cart_v4') || '[]'),
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const money = value => value == null ? 'Quote' : `$${Number(value).toFixed(2)}`;
const esc = s => String(s ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
const currentName = item => state.lang === 'es' ? item.name_es : item.name_en;
const currentDescription = item => state.lang === 'es' ? item.description_es : item.description_en;
const sortOptions = [
  {key:'popular', label_en:'Popular', label_es:'Popular'},
  {key:'price_asc', label_en:'Price', label_es:'Precio'},
  {key:'price_desc', label_en:'Price high', label_es:'Precio alto'},
  {key:'name', label_en:'Name', label_es:'Nombre'}
];
const categoryFilterDefinitions = [
  {key:'all', label_en:'All products', label_es:'Todo'},
  {key:'fresh_bread', label_en:'Fresh bread', label_es:'Pan fresco', categories:['savory','oaxacan','fluffy','dense']},
  {key:'sweet_pastries', label_en:'Sweet pastries', label_es:'Pan dulce', categories:['empanadas','pastries','donuts_churros','cookies']},
  {key:'cakes_desserts', label_en:'Cakes & desserts', label_es:'Pasteles y postres', categories:['cakes','desserts']},
  {key:'seasonal_items', label_en:'Seasonal', label_es:'Temporada', match:p => Boolean(p.is_seasonal) || p.category_key === 'seasonal'}
];

const copy = {
  en: {
    nav_menu:'Menu', nav_wholesale:'Wholesale', nav_quotes:'Cakes & seasonal', nav_partners:'Partners', nav_admin:'Admin', account:'Account',
    eyebrow:'Oaxacan breads • cakes • pickup orders', hero_title:'Order Mexican bread with real pickup availability.', hero_text:'Browse real bakery photos, see what is ready, and add favorites for pickup in Morristown.', shop_now:'Shop the menu', request_quote:'Request a quote',
    pain_1_title:'Find bread visually', pain_1:'Spanish and English names, aliases, shapes, and fillings.', pain_2_title:'Avoid bad pickups', pain_2:'Hours, capacity, inventory, and lead times are checked before ordering.', pain_3_title:'Wholesale built in', pain_3:'Premium pricing, applications, standing orders, and bulk bundles.', pain_4_title:'Quotes are real workflows', pain_4:'Cakes, Rosca, and Pan de Muerto collect the details staff need.',
    find_bread:'Find your bread', bulk_friendly:'Bulk friendly only', orderable_now:'Orderable now only', search_note:'Search accepts English, Spanish, visual words, and common misspellings.', catalog_eyebrow:'Expanded catalog', catalog_title:'Menu', catalog_copy:'Prices use the public menu where available. Items with variable decoration or seasonal sizing use quote requests.',
    quote_eyebrow:'Cakes and seasonal bread', quote_title:'Quote forms collect the missing details before staff call back.', quote_copy:'Custom cakes, Pan de Muerto, and Rosca de Reyes need sizes, fillings, decoration notes, event dates, and pickup timing.', start_quote:'Start quote request', cake_quote:'Custom cakes', cake_quote_desc:'Flavor, filling, inscription, reference image, budget, event date.', rosca_quote_desc:'Size, quantity, pickup window, hidden figurine planning.', muerto_quote_desc:'White sugar, pink sugar, or Oaxacan yema face style.',
    wholesale_eyebrow:'Premium customer flow', wholesale_title:'For shops that buy bread every week', wholesale_copy:'Apply for premium pricing, save standing orders, and reorder bulk bread without rebuilding the basket.', apply_wholesale:'Apply for wholesale', submit_application:'Submit application', standing_orders:'Standing orders', standing_copy:'Approved premium accounts can save recurring orders such as “60 bolillos every Friday at 7:30 AM.”',
    partners_eyebrow:'Community shelf', partners_title:'Businesses buying from the bakery can be promoted here.', partners_copy:'The app requires consent before publishing real partner cards. Demo cards remain marked until replaced.', basket:'Basket', promo_code:'Promo code', subtotal:'Subtotal', checkout:'Checkout', login:'Login', register:'Register', login_title:'Login', login_note:'Demo credentials are in the README. Passwords are intentionally not prefilled.', register_title:'Create customer account', create_account:'Create account', checkout_title:'Pickup checkout', contact_info:'Contact', pickup_info:'Pickup', pay_pickup:'Pay at pickup', deposit_pending:'Deposit to be collected', place_order:'Place pickup order', quote_dialog_title:'Quote request', quote_item:'Item', details:'Details', submit_quote:'Submit quote request'
  },
  es: {
    nav_menu:'Menú', nav_wholesale:'Mayoreo', nav_quotes:'Pasteles y temporada', nav_partners:'Negocios', nav_admin:'Admin', account:'Cuenta',
    eyebrow:'Panes oaxaqueños • pasteles • pedidos', hero_title:'Ordena pan mexicano con disponibilidad real para recoger.', hero_text:'Mira fotos reales, revisa lo que está listo y agrega tus favoritos para recoger en Morristown.', shop_now:'Ver menú', request_quote:'Pedir cotización',
    pain_1_title:'Encuentra por forma', pain_1:'Nombres en español e inglés, alias, formas y rellenos.', pain_2_title:'Evita malos horarios', pain_2:'El sistema revisa horario, cupo, inventario y anticipación.', pain_3_title:'Mayoreo incluido', pain_3:'Precios premium, solicitudes, pedidos fijos y paquetes grandes.', pain_4_title:'Cotizaciones útiles', pain_4:'Pasteles, Rosca y Pan de Muerto capturan los datos que necesita el personal.',
    find_bread:'Busca tu pan', bulk_friendly:'Solo mayoreo', orderable_now:'Solo disponible para ordenar', search_note:'La búsqueda acepta español, inglés, palabras visuales y errores comunes.', catalog_eyebrow:'Catálogo ampliado', catalog_title:'Menú', catalog_copy:'Los precios usan el menú público cuando está disponible. Decoración variable y temporada usan cotización.',
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
  renderProductSkeletons();
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
  const priceFilter = $('#priceFilter');
  if(priceFilter){
    $$('option', priceFilter).forEach(option => { option.textContent = priceFilterLabel(option.value); });
    priceFilter.value = state.price;
  }
  updateSortButton();
  renderProducts(); renderCart(); renderPartners(); renderStatus(); renderAccount(); renderQuoteProducts(); renderReviewProducts(); renderCampaigns(); renderVisualChips(); renderBakeryCase(); renderCampaignCapacity(); renderFilterSummary();
}

function renderStatus(){
  const s = state.data?.store_status;
  if(!s) return;
  const label = state.lang === 'es' ? s.message_es : s.message_en;
  $('#storeStatus').innerHTML = `<span class="status-dot ${s.is_open ? '' : 'closed'}"></span><div><strong>${label}</strong><br><small>${state.lang === 'es' ? s.day_es : s.day_en}: ${s.opens_at || '—'}–${s.closes_at || '—'}</small></div>`;
}

function renderCategories(){
  const wrap = $('#categoryChips');
  const cats = categoryFilterDefinitions;
  wrap.innerHTML = cats.map(cat => `<button class="chip ${state.category === cat.key ? 'active' : ''}" data-category="${cat.key}" type="button" aria-pressed="${state.category === cat.key}">${categoryFilterLabel(cat.key)}</button>`).join('');
  $$('.chip', wrap).forEach(btn => btn.addEventListener('click', () => { state.category = btn.dataset.category; renderCategories(); renderProducts(); renderFilterSummary(); }));
}

function renderVisualChips(){
  const wrap = $('#visualChips'); if(!wrap || !state.data) return;
  const available = new Set((state.data.visual_shapes || []).map(v => v.visual_shape || 'other'));
  const preferred = ['all', 'filled', 'flaky', 'cookie', 'cake', 'roll'];
  const unique = preferred.filter(shape => shape === 'all' || available.has(shape));
  wrap.innerHTML = unique.map(shape => `<button class="chip ${state.visual === shape ? 'active' : ''}" data-visual="${esc(shape)}" type="button" aria-pressed="${state.visual === shape}">${visualLabel(shape)}</button>`).join('');
  $$('[data-visual]', wrap).forEach(btn => btn.addEventListener('click', () => { state.visual = btn.dataset.visual; renderVisualChips(); renderProducts(); renderFilterSummary(); }));
}

function visualLabel(shape){
  const labels = {all:'All shapes', shell:'Shells', pig:'Pigs', heart:'Hearts', ring:'Rings', filled:'Filled', flaky:'Flaky', cookie:'Cookies', slice:'Slices', cake:'Cakes', roll:'Rolls', other:'Other'};
  const labelsEs = {all:'Todas', shell:'Conchas', pig:'Marranitos', heart:'Corazones', ring:'Roscas/aretes', filled:'Rellenos', flaky:'Hojaldres', cookie:'Galletas', slice:'Rebanadas', cake:'Pasteles', roll:'Bolillos', other:'Otros'};
  return state.lang === 'es' ? (labelsEs[shape] || shape) : (labels[shape] || shape);
}

function categoryLabel(key){
  if(key === 'all') return state.lang === 'es' ? 'Todo' : 'All products';
  const cat = state.data?.categories?.find(c => c.key === key);
  if(!cat) return key;
  return state.lang === 'es' ? cat.name_es : cat.name_en;
}

function categoryFilterLabel(key){
  const item = categoryFilterDefinitions.find(cat => cat.key === key);
  if(item) return state.lang === 'es' ? item.label_es : item.label_en;
  return categoryLabel(key);
}

function productMatchesCategoryFilter(product, key = state.category){
  if(key === 'all') return true;
  const item = categoryFilterDefinitions.find(cat => cat.key === key);
  if(item?.categories) return item.categories.includes(product.category_key);
  if(item?.match) return item.match(product);
  return product.category_key === key;
}

function priceFilterLabel(key = state.price){
  const labels = {
    all: {en:'Any price', es:'Cualquier precio'},
    under_1: {en:'Under $1', es:'Menos de $1'},
    under_3: {en:'Under $3', es:'Menos de $3'},
    cakes: {en:'Cakes and trays', es:'Pasteles y charolas'}
  };
  const label = labels[key] || labels.all;
  return state.lang === 'es' ? label.es : label.en;
}

function hasActiveCatalogFilters(){
  return Boolean(
    state.query ||
    state.category !== 'all' ||
    state.visual !== 'all' ||
    state.price !== 'all' ||
    $('#bulkOnly')?.checked ||
    $('#orderableOnly')?.checked
  );
}

const productSectionDefinitions = [
  {
    key:'popular_today',
    title_en:'Popular today',
    title_es:'Popular hoy',
    note_en:'Fast-moving breads and bakery staples customers ask for most.',
    note_es:'Panes y básicos que los clientes piden con más frecuencia.',
    limit:6,
    match:p => ['concha','bolillo','alcatraz','empanada-manzana','banderilla','tres-leches-rebanada'].includes(p.slug) && Boolean(p.image_url)
  },
  {
    key:'fresh_bread',
    title_en:'Fresh bread',
    title_es:'Pan fresco',
    note_en:'Daily rolls, Oaxacan breads, conchas, and fluffy pan dulce.',
    note_es:'Bolillos, panes oaxaqueños, conchas y pan dulce esponjado.',
    limit:9,
    categories:['savory','oaxacan','fluffy','dense']
  },
  {
    key:'sweet_pastries',
    title_en:'Sweet pastries',
    title_es:'Pan dulce y hojaldres',
    note_en:'Filled empanadas, cookies, donuts, churros, and flaky pastries.',
    note_es:'Empanadas, galletas, donas, churros y hojaldres.',
    limit:9,
    categories:['empanadas','pastries','donuts_churros','cookies']
  },
  {
    key:'cakes_desserts',
    title_en:'Cakes and desserts',
    title_es:'Pasteles y postres',
    note_en:'Tres leches, flan, cake slices, trays, and custom cake options.',
    note_es:'Tres leches, flan, rebanadas, charolas y opciones de pastel.',
    limit:6,
    categories:['cakes','desserts']
  },
  {
    key:'seasonal_items',
    title_en:'Seasonal items',
    title_es:'Pan de temporada',
    note_en:'Holiday breads and special-order seasonal favorites.',
    note_es:'Panes de temporada y favoritos especiales por pedido.',
    limit:6,
    match:p => Boolean(p.is_seasonal) || p.category_key === 'seasonal'
  }
];

function sectionTitle(section){
  return state.lang === 'es' ? section.title_es : section.title_en;
}

function sectionNote(section){
  return state.lang === 'es' ? section.note_es : section.note_en;
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

function sortLabel(){
  const current = sortOptions.find(opt => opt.key === state.sort) || sortOptions[0];
  return state.lang === 'es' ? current.label_es : current.label_en;
}

function updateSortButton(){
  const btn = $('#sortButton');
  if(btn) btn.textContent = `${state.lang === 'es' ? 'Orden' : 'Sort'}: ${sortLabel()}`;
}

function cycleSort(){
  const index = Math.max(0, sortOptions.findIndex(opt => opt.key === state.sort));
  state.sort = sortOptions[(index + 1) % sortOptions.length].key;
  updateSortButton();
  renderProducts();
}

function filteredProducts(){
  const q = normalize(state.query);
  const products = state.data.products.filter(p => {
    if(!productMatchesCategoryFilter(p)) return false;
    if(state.visual !== 'all' && (p.visual_shape || 'other') !== state.visual) return false;
    if($('#bulkOnly')?.checked && !p.is_bulk_friendly) return false;
    if($('#orderableOnly')?.checked && !p.can_order) return false;
    const productPrice = Number(p.effective_price ?? p.base_price ?? 0);
    if(state.price === 'under_1' && !(productPrice > 0 && productPrice < 1)) return false;
    if(state.price === 'under_3' && !(productPrice > 0 && productPrice < 3)) return false;
    if(state.price === 'cakes' && !['cakes','desserts'].includes(p.category_key)) return false;
    if(q && !productSearchBlob(p).includes(q)) return false;
    return true;
  });
  return products.sort((a,b) => {
    if(state.sort === 'price_asc') return Number(a.effective_price ?? 999999) - Number(b.effective_price ?? 999999);
    if(state.sort === 'price_desc') return Number(b.effective_price ?? -1) - Number(a.effective_price ?? -1);
    if(state.sort === 'name') return currentName(a).localeCompare(currentName(b), state.lang === 'es' ? 'es' : 'en');
    return Number(b.can_order || 0) - Number(a.can_order || 0) || Number(b.is_bulk_friendly || 0) - Number(a.is_bulk_friendly || 0) || currentName(a).localeCompare(currentName(b), state.lang === 'es' ? 'es' : 'en');
  });
}

function renderProductSkeletons(){
  const grid = $('#productGrid');
  if(!grid) return;
  grid.innerHTML = `<section class="product-section" aria-hidden="true"><div class="product-grid">${Array.from({length:6}, () => `<article class="product-card skeleton-card"><div class="skeleton-image"></div><div class="skeleton-lines"><span></span><span></span><span></span></div></article>`).join('')}</div></section>`;
}

function activeFilterChips(){
  const chips = [];
  if(state.query) chips.push({key:'query', label:`"${state.query}"`});
  if(state.category !== 'all') chips.push({key:'category', label:categoryFilterLabel(state.category)});
  if(state.visual !== 'all') chips.push({key:'visual', label:visualLabel(state.visual)});
  if(state.price !== 'all') chips.push({key:'price', label:priceFilterLabel()});
  if($('#bulkOnly')?.checked) chips.push({key:'bulk', label:state.lang === 'es' ? 'Mayoreo' : 'Bulk friendly'});
  if($('#orderableOnly')?.checked) chips.push({key:'orderable', label:state.lang === 'es' ? 'Disponible' : 'Orderable now'});
  return chips;
}

function renderFilterSummary(){
  const wrap = $('#filterSummary');
  const count = $('#filterCount');
  if(!wrap) return;
  const chips = activeFilterChips();
  if(count){
    count.hidden = chips.length === 0;
    count.textContent = chips.length;
  }
  wrap.innerHTML = chips.map(chip => `<button class="filter-chip" data-remove-filter="${chip.key}" type="button">${esc(chip.label)} <span aria-hidden="true">×</span></button>`).join('');
  $$('[data-remove-filter]', wrap).forEach(btn => btn.addEventListener('click', () => removeFilter(btn.dataset.removeFilter)));
}

function removeFilter(key){
  if(key === 'query'){ state.query = ''; $('#searchInput').value = ''; }
  if(key === 'category'){ state.category = 'all'; renderCategories(); }
  if(key === 'visual'){ state.visual = 'all'; renderVisualChips(); }
  if(key === 'price'){ state.price = 'all'; $('#priceFilter').value = 'all'; }
  if(key === 'bulk') $('#bulkOnly').checked = false;
  if(key === 'orderable') $('#orderableOnly').checked = false;
  renderProducts();
  renderFilterSummary();
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

function buildProductSections(products){
  const sections = [];
  const seen = new Set();
  for(const definition of productSectionDefinitions){
    const items = products.filter(product => {
      if(seen.has(product.slug)) return false;
      if(definition.categories) return definition.categories.includes(product.category_key);
      return definition.match ? definition.match(product) : false;
    });
    if(!items.length) continue;
    items.forEach(item => seen.add(item.slug));
    sections.push({...definition, items});
  }
  const remaining = products.filter(product => !seen.has(product.slug));
  if(remaining.length){
    sections.push({
      key:'more_items',
      title_en:'More bakery items',
      title_es:'Más productos',
      note_en:'Additional breads and pastries from the full catalog.',
      note_es:'Más panes y postres del catálogo completo.',
      limit:9,
      items:remaining
    });
  }
  return sections;
}

function productAvailability(product){
  if(product.order_mode === 'quote') return {
    label: state.lang === 'es' ? 'Cotización requerida' : 'Quote required',
    className:'quote'
  };
  if(product.stock_policy === 'track' && Number(product.stock_count) < 20) return {
    label: state.lang === 'es' ? `Solo ${product.stock_count}` : `Only ${product.stock_count} left`,
    className:'low'
  };
  if(product.stock_policy === 'track') return {
    label: state.lang === 'es' ? 'Disponible hoy' : 'Available today',
    className:''
  };
  return {
    label: state.lang === 'es' ? 'Por pedido' : 'Made to order',
    className:''
  };
}

function renderProductCard(product, template){
  const node = template.content.firstElementChild.cloneNode(true);
  const titleId = `product-title-${String(product.slug).replace(/[^a-z0-9_-]/gi, '-')}`;
  const descId = `product-desc-${String(product.slug).replace(/[^a-z0-9_-]/gi, '-')}`;
  node.setAttribute('aria-labelledby', titleId);
  node.setAttribute('aria-describedby', descId);
  node.tabIndex = 0;
  node.addEventListener('click', event => {
    if(event.target.closest('button, select, input, textarea, a')) return;
    openProductDetails(product);
  });
  node.addEventListener('keydown', event => {
    if((event.key === 'Enter' || event.key === ' ') && !event.target.closest('button, select, input, textarea, a')){
      event.preventDefault();
      openProductDetails(product);
    }
  });

  setProductArt($('.product-art', node), product);
  const title = $('h3', node);
  title.id = titleId;
  title.textContent = currentName(product);
  const description = $('p', node);
  description.id = descId;
  description.textContent = currentDescription(product);

  const availability = productAvailability(product);
  const stock = $('.stock-badge', node);
  stock.textContent = availability.label;
  if(availability.className) stock.classList.add(availability.className);
  $('.category-badge', node).textContent = categoryLabel(product.category_key);

  const variantBox = $('.variant-box', node);
  const groups = groupVariants(product.variants || []);
  variantBox.innerHTML = Object.entries(groups).map(([type, variants]) => `<select data-variant-type="${type}" aria-label="${esc(type.replace('_',' '))}"><option value="">${type.replace('_',' ')}</option>${variants.map(v => `<option value="${v.id}" ${v.is_default ? 'selected' : ''}>${state.lang === 'es' ? v.name_es : v.name_en}${Number(v.price_delta) ? ` +${money(v.price_delta)}` : ''}</option>`).join('')}</select>`).join('');
  $$('select[data-variant-type]', variantBox).forEach(sel => sel.addEventListener('change', () => updateCardCartControl(product, node)));

  $('.allergen-row', node).innerHTML = (product.allergens || []).slice(0,4).map(a => `<span>${state.lang === 'es' ? a.name_es : a.name_en}</span>`).join('');
  $('.product-trust', node).innerHTML = `<span>${esc(product.visual_shape || 'case')}</span>`;
  $('.favorite-btn', node).addEventListener('click', () => toggleFavorite(product));
  $('.details-btn', node).addEventListener('click', () => openProductDetails(product));
  updateCardCartControl(product, node);
  $('.source-line', node).textContent = product.price_basis || '';
  return node;
}

function renderProducts(){
  if(!state.data) return;
  const container = $('#productGrid');
  const template = $('#productTemplate');
  const products = filteredProducts();
  const isFiltering = hasActiveCatalogFilters();
  $('#productCount').textContent = `${products.length}`;
  renderFilterSummary();
  if(!products.length){
    container.innerHTML = `<div class="empty-state"><b>${state.lang === 'es' ? 'No se encontraron productos.' : 'No products found.'}</b><button id="emptyResetFilters" class="secondary-action" type="button">${state.lang === 'es' ? 'Limpiar filtros' : 'Reset filters'}</button></div>`;
    $('#emptyResetFilters')?.addEventListener('click', resetFilters);
    return;
  }

  container.innerHTML = '';
  for(const section of buildProductSections(products)){
    const sectionNode = document.createElement('section');
    const headingId = `section-${section.key}`;
    const expanded = isFiltering || Boolean(state.expandedSections[section.key]);
    const limit = section.limit || 9;
    const visibleItems = expanded ? section.items : section.items.slice(0, limit);
    sectionNode.className = 'product-section';
    sectionNode.setAttribute('aria-labelledby', headingId);
    sectionNode.innerHTML = `<div class="product-section-header"><div><h2 id="${headingId}">${esc(sectionTitle(section))}</h2><p>${esc(sectionNote(section))}</p><small>${section.items.length} ${section.items.length === 1 ? 'item' : 'items'}</small></div>${!expanded && section.items.length > limit ? `<button class="view-section-button" data-section="${section.key}" type="button">${state.lang === 'es' ? 'Ver todo' : 'View all'}</button>` : ''}</div><div class="product-grid"></div>`;
    const grid = $('.product-grid', sectionNode);
    visibleItems.forEach(product => grid.appendChild(renderProductCard(product, template)));
    container.appendChild(sectionNode);
  }
  $$('[data-section]', container).forEach(button => button.addEventListener('click', () => {
    state.expandedSections[button.dataset.section] = true;
    renderProducts();
  }));
}

function selectedVariants(card){
  return $$('select[data-variant-type]', card).map(sel => Number(sel.value)).filter(Boolean);
}
function cartItemFor(product, variantIds){
  const key = cartKey(product.slug, variantIds);
  return state.cart.find(item => item.key === key);
}
function updateCardPrice(product, card){
  const ids = selectedVariants(card);
  $('.price', card).textContent = product.order_mode === 'quote' ? (state.lang === 'es' ? 'Cotizar' : 'Quote') : money(Number(product.effective_price || product.base_price || 0) + variantDelta(product, ids));
}
function keepCardControlVisible(card){
  requestAnimationFrame(() => {
    const control = $('.card-cart-control', card);
    if(!control) return;
    const rect = control.getBoundingClientRect();
    const bar = $('#cartBar');
    const barTop = bar && !bar.hidden ? bar.getBoundingClientRect().top : window.innerHeight;
    if(rect.bottom > barTop - 16 || rect.top < Number.parseInt(getComputedStyle(document.documentElement).getPropertyValue('--top-bar-height') || '72', 10)){
      const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      card.scrollIntoView({block:'center', inline:'nearest', behavior:reduceMotion ? 'auto' : 'smooth'});
    }
  });
}
function updateCardCartControl(product, card){
  updateCardPrice(product, card);
  const control = $('.card-cart-control', card);
  const ids = selectedVariants(card);
  if(product.order_mode === 'quote'){
    control.innerHTML = `<button class="add-button quote" type="button">${state.lang === 'es' ? 'Cotizar' : 'Quote'}</button>`;
    $('button', control).addEventListener('click', () => openQuote(product.slug));
    return;
  }
  const existing = cartItemFor(product, ids);
  if(existing){
    control.innerHTML = `<div class="inline-qty" aria-label="${esc(`Quantity for ${currentName(product)}`)}"><button data-card-dec type="button" aria-label="${esc(`Remove one ${currentName(product)}`)}">−</button><span>${existing.quantity}</span><button data-card-inc type="button" aria-label="${esc(`Add one more ${currentName(product)}`)}">+</button></div>`;
    $('[data-card-inc]', control).addEventListener('click', () => { existing.quantity++; saveCart(); updateCardCartControl(product, card); keepCardControlVisible(card); announceCart(`${currentName(product)} quantity ${existing.quantity}.`); });
    $('[data-card-dec]', control).addEventListener('click', () => { existing.quantity--; if(existing.quantity <= 0) state.cart = state.cart.filter(item => item !== existing); saveCart(); updateCardCartControl(product, card); keepCardControlVisible(card); announceCart(existing.quantity > 0 ? `${currentName(product)} quantity ${existing.quantity}.` : `${currentName(product)} removed from cart.`); });
  } else {
    control.innerHTML = `<button class="add-button" type="button" aria-label="${esc(`Add ${currentName(product)} to cart`)}">${state.lang === 'es' ? 'Agregar' : 'Add'}</button>`;
    $('button', control).addEventListener('click', () => { addProductFromCard(product, card); updateCardCartControl(product, card); keepCardControlVisible(card); });
  }
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
function cartTotals(){
  let subtotal = 0;
  let count = 0;
  for(const item of state.cart){
    const p = state.data?.products?.find(x => x.slug === item.slug);
    if(!p) continue;
    const unit = Number(p.effective_price || p.base_price || 0) + variantDelta(p, item.variant_ids || []);
    subtotal += unit * item.quantity;
    count += item.quantity;
  }
  return {count, subtotal};
}
function announceCart(message){
  const live = $('#cartLive');
  if(live) live.textContent = message;
}
function addToCart(slug, qty = 1, variantIds = []){
  const p = state.data.products.find(x => x.slug === slug); if(!p) return;
  const key = cartKey(slug, variantIds);
  const existing = state.cart.find(item => item.key === key);
  if(existing) existing.quantity += qty; else state.cart.push({key, slug, quantity: qty, variant_ids: variantIds, variant_label: variantLabel(p, variantIds)});
  saveCart();
  const totals = cartTotals();
  announceCart(`${state.lang === 'es' ? 'Agregado' : 'Added'} ${currentName(p)}. ${totals.count} ${totals.count === 1 ? 'item' : 'items'} in cart. ${money(totals.subtotal)} total.`);
}
function addBundle(slug){
  const b = state.data.bundles.find(x => x.slug === slug); if(!b) return;
  const items = JSON.parse(b.items_json || '{}');
  Object.entries(items).forEach(([productSlug, qty]) => addToCart(productSlug, Number(qty), []));
  renderProducts();
}
function renderCart(){
  const totals = cartTotals();
  const count = totals.count;
  $('#cartCount').textContent = count;
  const bar = $('#cartBar');
  if(bar){
    bar.hidden = count === 0;
    $('#cartBarCount').textContent = `${count} ${count === 1 ? 'item' : 'items'}`;
    $('#cartBarSubtotal').textContent = money(totals.subtotal);
  }
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
  $$('[data-inc]', wrap).forEach(b => b.addEventListener('click', () => { state.cart[Number(b.dataset.inc)].quantity++; saveCart(); renderProducts(); }));
  $$('[data-dec]', wrap).forEach(b => b.addEventListener('click', () => { const i = state.cart[Number(b.dataset.dec)]; i.quantity--; if(i.quantity <= 0) state.cart.splice(Number(b.dataset.dec),1); saveCart(); renderProducts(); }));
  $$('[data-remove]', wrap).forEach(b => b.addEventListener('click', () => { state.cart.splice(Number(b.dataset.remove),1); saveCart(); renderProducts(); }));
}
function openCart(){ $('#cartDrawer').classList.add('open'); $('#drawerShade').classList.add('open'); $('#cartDrawer').setAttribute('aria-hidden','false'); }
function closeCart(){ $('#cartDrawer').classList.remove('open'); $('#drawerShade').classList.remove('open'); $('#cartDrawer').setAttribute('aria-hidden','true'); }

let filterTrigger = null;
const desktopFiltersQuery = window.matchMedia('(min-width: 960px)');
function syncFilterMode(){
  const sheet = $('#filterSheet');
  const backdrop = $('#filterSheetBackdrop');
  if(!sheet || !backdrop) return;
  if(desktopFiltersQuery.matches){
    sheet.classList.remove('open');
    sheet.setAttribute('aria-hidden', 'false');
    sheet.setAttribute('role', 'region');
    sheet.removeAttribute('aria-modal');
    backdrop.hidden = true;
    backdrop.classList.remove('open');
    document.body.classList.remove('sheet-open');
  } else {
    sheet.setAttribute('role', 'dialog');
    sheet.setAttribute('aria-modal', 'true');
    if(!sheet.classList.contains('open')) sheet.setAttribute('aria-hidden', 'true');
  }
}
function openFilters(){
  if(desktopFiltersQuery.matches) return;
  const sheet = $('#filterSheet');
  const backdrop = $('#filterSheetBackdrop');
  filterTrigger = document.activeElement;
  backdrop.hidden = false;
  sheet.setAttribute('aria-hidden', 'false');
  sheet.classList.add('open');
  backdrop.classList.add('open');
  document.body.classList.add('sheet-open');
  $('#closeFilters')?.focus();
}
function closeFilters(){
  const sheet = $('#filterSheet');
  const backdrop = $('#filterSheetBackdrop');
  if(desktopFiltersQuery.matches){ syncFilterMode(); return; }
  sheet.classList.remove('open');
  backdrop.classList.remove('open');
  document.body.classList.remove('sheet-open');
  sheet.setAttribute('aria-hidden', 'true');
  backdrop.hidden = true;
  if(filterTrigger && typeof filterTrigger.focus === 'function') filterTrigger.focus();
}
function resetFilters(){
  state.category = 'all';
  state.visual = 'all';
  state.price = 'all';
  state.query = '';
  $('#searchInput').value = '';
  $('#priceFilter').value = 'all';
  $('#bulkOnly').checked = false;
  $('#orderableOnly').checked = false;
  renderCategories();
  renderVisualChips();
  renderProducts();
  renderFilterSummary();
}
function trapFilterFocus(event){
  const sheet = $('#filterSheet');
  if(desktopFiltersQuery.matches) return;
  if(sheet.getAttribute('aria-hidden') === 'true') return;
  if(event.key === 'Escape'){ closeFilters(); return; }
  if(event.key !== 'Tab') return;
  const focusable = $$('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])', sheet).filter(el => !el.disabled && el.offsetParent !== null);
  if(!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if(event.shiftKey && document.activeElement === first){ event.preventDefault(); last.focus(); }
  else if(!event.shiftKey && document.activeElement === last){ event.preventDefault(); first.focus(); }
}

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
  $('#cartBarButton')?.addEventListener('click', openCart);
  $('#searchInput').addEventListener('input', e => { state.query = e.target.value; renderProducts(); renderFilterSummary(); });
  $('#priceFilter')?.addEventListener('change', e => { state.price = e.target.value; renderProducts(); renderFilterSummary(); });
  $('#bulkOnly').addEventListener('change', () => { renderProducts(); renderFilterSummary(); });
  $('#orderableOnly').addEventListener('change', () => { renderProducts(); renderFilterSummary(); });
  $('#openFilters')?.addEventListener('click', openFilters);
  $('#closeFilters')?.addEventListener('click', closeFilters);
  $('#filterSheetBackdrop')?.addEventListener('click', closeFilters);
  $('#resetFilters')?.addEventListener('click', resetFilters);
  $('#applyFilters')?.addEventListener('click', closeFilters);
  $('#sortButton')?.addEventListener('click', cycleSort);
  desktopFiltersQuery.addEventListener('change', syncFilterMode);
  syncFilterMode();
  document.addEventListener('keydown', trapFilterFocus);
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
