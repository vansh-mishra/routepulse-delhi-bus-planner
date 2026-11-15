(() => {
  const form = document.getElementById('journey-form');
  if (!form) return;
  const originInput = document.getElementById('origin-search');
  const destInput = document.getElementById('destination-search');
  const originId = document.getElementById('origin-id');
  const destId = document.getElementById('destination-id');
  const resultsPanel = document.getElementById('results-panel');
  const planButton = document.getElementById('plan-button');
  const loggedIn = document.body.dataset.loggedIn === 'true';
  let map, routeLayers = [], liveLayer;
  const palette = ['#2365cf','#16a37a','#d68a32'];

  function esc(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function setupMap() {
    if (!window.L) return;
    map = L.map('route-map', {zoomControl:true, scrollWheelZoom:false}).setView([28.63,77.18], 10.8);
    liveLayer = L.layerGroup().addTo(map);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>', maxZoom:19}).addTo(map);
  }
  setupMap();
  function clearMap() { routeLayers.forEach(layer => map && map.removeLayer(layer)); routeLayers=[]; }
  function drawPlan(data) {
    if (!map) return;
    clearMap();
    const bounds=[];
    (data.map_legs || []).forEach((leg, i) => {
      const coords = leg.geometry || [];
      if (coords.length > 1) {
        const line = L.polyline(coords, {color:palette[i%palette.length], weight:5, opacity:.85, lineCap:'round'}).addTo(map);
        routeLayers.push(line); coords.forEach(p=>bounds.push(p));
      }
    });
    const o = data.origin, d = data.destination;
    if (o && o.stop_lat && o.stop_lon) routeLayers.push(L.circleMarker([o.stop_lat,o.stop_lon],{radius:8,color:'#fff',weight:3,fillColor:'#1d9a70',fillOpacity:1}).addTo(map).bindPopup('Origin: '+esc(o.stop_name)));
    if (d && d.stop_lat && d.stop_lon) routeLayers.push(L.circleMarker([d.stop_lat,d.stop_lon],{radius:8,color:'#fff',weight:3,fillColor:'#d97732',fillOpacity:1}).addTo(map).bindPopup('Destination: '+esc(d.stop_name)));
    if (bounds.length) map.fitBounds(bounds,{padding:[25,25],maxZoom:14});
    else if (o && o.stop_lat) map.setView([o.stop_lat,o.stop_lon],13);
    setTimeout(()=>map.invalidateSize(),100);
  }
  function setupAutocomplete(input, hidden, list) {
    let timer, controller;
    input.addEventListener('input', () => {
      hidden.value = '';
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 2) { list.innerHTML=''; list.classList.remove('show'); return; }
      timer=setTimeout(async()=>{
        if (controller) controller.abort(); controller=new AbortController();
        try {
          const r=await fetch('/api/stops?q='+encodeURIComponent(q),{signal:controller.signal});
          const data=await r.json();
          list.innerHTML=(data.results||[]).map(s=>`<button type="button" class="suggestion-item" data-id="${esc(s.stop_id)}" data-name="${esc(s.stop_name)}"><span class="suggestion-pin">●</span><span><strong>${esc(s.stop_name)}</strong><small>Delhi bus stop · ${esc(s.stop_id)}</small></span></button>`).join('') || '<div class="suggestion-empty">No matching stop found. Try another name.</div>';
          list.classList.add('show');
        } catch(e) { if(e.name!=='AbortError') list.innerHTML='<div class="suggestion-empty">Stop search is unavailable. Please retry.</div>'; }
      },220);
    });
    list.addEventListener('click', e=>{
      const btn=e.target.closest('.suggestion-item'); if(!btn)return;
      input.value=btn.dataset.name; hidden.value=btn.dataset.id; list.innerHTML=''; list.classList.remove('show');
    });
    document.addEventListener('click',e=>{if(!input.parentElement.contains(e.target))list.classList.remove('show');});
  }
  setupAutocomplete(originInput,originId,document.getElementById('origin-suggestions'));
  setupAutocomplete(destInput,destId,document.getElementById('destination-suggestions'));
  document.querySelectorAll('.clear-stop').forEach(btn=>btn.addEventListener('click',()=>{
    const key=btn.dataset.clear; if(key==='origin'){originInput.value='';originId.value='';originInput.focus();}else{destInput.value='';destId.value='';destInput.focus();}
  }));
  document.getElementById('swap-stops').addEventListener('click',()=>{
    [originInput.value,destInput.value]=[destInput.value,originInput.value];
    [originId.value,destId.value]=[destId.value,originId.value];
  });
  const sample = document.getElementById('sample-journey');
  if(sample) sample.addEventListener('click',async()=>{
    try {
      const [a,b]=await Promise.all([
        fetch('/api/stops?q='+encodeURIComponent('Kashmere Gate City Bus Terminal')).then(r=>r.json()),
        fetch('/api/stops?q='+encodeURIComponent('Nehru Place Terminal')).then(r=>r.json())
      ]);
      const origin=(a.results||[]).find(x=>x.stop_name.toLowerCase()==='kashmere gate city bus terminal') || a.results?.[0];
      const dest=(b.results||[]).find(x=>x.stop_name.toLowerCase()==='nehru place terminal') || b.results?.[0];
      if(origin&&dest){originInput.value=origin.stop_name;originId.value=origin.stop_id;destInput.value=dest.stop_name;destId.value=dest.stop_id;document.getElementById('departure').value='2026-11-17T08:30';}
    } catch(e) { /* The user can still search manually. */ }
  });
  function formatMinutes(m){const n=Math.round(m);const h=Math.floor(n/60),mm=n%60;return h?`${h}h ${mm}m`:`${mm} min`;}
  function renderResults(data){
    drawPlan(data);
    if(!data.options?.length){resultsPanel.innerHTML='<div class="empty-results"><div class="empty-icon">⌁</div><h3>No scheduled journey found.</h3><p>Try a different departure time or nearby stop. This first release searches direct trips and one-transfer connections.</p></div>';return;}
    const cards=data.options.map((o,i)=>{
      const legs=o.legs.map((l,j)=>`<div class="journey-leg"><div class="leg-rail"><span class="leg-node"></span><span class="leg-track"></span><span class="leg-node end-node"></span></div><div class="leg-body"><div class="leg-top"><span class="route-badge" style="--route-color:${palette[(i+j)%palette.length]}">${esc(l.route)}</span><strong>${esc(l.departure)} <span>→</span> ${esc(l.arrival)}</strong></div><p><strong>${esc(l.from_stop)}</strong> to <strong>${esc(l.to_stop)}</strong></p><small>${esc(l.route_name)} · ${formatMinutes(l.ride_minutes)} on bus</small></div></div>`).join('');
      const transfer=o.transfer_count?`<span class="journey-meta">1 transfer at ${esc(o.transfer_stop)}</span>`:'<span class="journey-meta">Direct service</span>';
      const demand=o.legs.map(l=>l.demand).filter(Boolean);
      const demandNote=demand.length?`<div class="demand-note"><span class="demand-dot"></span> October ticket records: ${demand.reduce((n,x)=>n+x.tickets,0).toLocaleString()} transactions for this route and departure hour. Demand context only.</div>`:'';
      return `<article class="journey-card ${i===0?'recommended':''}"><div class="journey-card-head"><div><span class="option-label">OPTION ${i+1} ${i===0?'<em>QUICKEST SCHEDULED</em>':''}</span><h3>${formatMinutes(o.total_minutes)}</h3><small>total estimated time, including selected walking buffers</small></div><div class="arrival-block"><span>ARRIVE</span><strong>${esc(o.arrival)}</strong></div></div><div class="journey-meta-row">${transfer}<span class="journey-meta">Wait ${formatMinutes(o.wait_minutes)}</span><span class="journey-meta">Walk ${o.walk_in_minutes}+${o.walk_out_minutes} min</span><span class="journey-meta">${o.legs.reduce((n,l)=>n+l.ride_minutes,0).toFixed(0)} min onboard</span></div><div class="journey-legs">${legs}</div>${o.transfer_count?`<div class="transfer-wait">Transfer wait: ${formatMinutes(o.transfer_wait_minutes)} at ${esc(o.transfer_stop)}</div>`:''}${demandNote}<div class="journey-card-foot"><span class="schedule-tag">GTFS timetable estimate</span>${loggedIn?`<button class="save-journey" data-option="${i}">☆ Save journey</button>`:`<a class="save-journey" href="/signup">Create account to save</a>`}</div></article>`;
    }).join('');
    resultsPanel.innerHTML=`<div class="results-heading"><div><div class="eyebrow muted-eyebrow">YOUR OPTIONS</div><h2>${data.options.length} journey option${data.options.length>1?'s':''}</h2><p>${esc(data.origin.stop_name)} → ${esc(data.destination.stop_name)} · Depart ${esc(data.departure)}</p></div><span class="result-count">${data.options.length} FOUND</span></div>${cards}<div class="results-footnote">${esc(data.model_note || 'Scheduled timetable baseline.')}</div>`;
    resultsPanel.querySelectorAll('.save-journey').forEach(btn=>btn.addEventListener('click',async()=>{
      if(!loggedIn)return; btn.disabled=true; btn.textContent='Saving…';
      const body={origin_id:originId.value,destination_id:destId.value,origin_name:originInput.value,destination_name:destInput.value,departure:document.getElementById('departure').value};
      try{const r=await fetch('/api/save-journey',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();btn.textContent=d.saved?'✓ Saved':'Try again';}catch(e){btn.textContent='Try again';} 
    }));
  }
  form.addEventListener('submit',async e=>{
    e.preventDefault();
    if(!originId.value||!destId.value){resultsPanel.innerHTML='<div class="empty-results error-empty"><div class="empty-icon">!</div><h3>Select both stops from the suggestions.</h3><p>Type at least two letters and choose one of the matching official GTFS stops.</p></div>';return;}
    planButton.disabled=true;planButton.innerHTML='<span class="button-spinner"></span> Finding journeys…';
    const params=new URLSearchParams({origin_id:originId.value,destination_id:destId.value,departure:document.getElementById('departure').value,walk_in:document.getElementById('walk-in').value,walk_out:document.getElementById('walk-out').value});
    try{const r=await fetch('/api/plan?'+params.toString());const data=await r.json();if(!r.ok)throw new Error(data.error||'Could not plan this journey.');renderResults(data);}
    catch(err){resultsPanel.innerHTML=`<div class="empty-results error-empty"><div class="empty-icon">!</div><h3>We couldn't plan this journey.</h3><p>${esc(err.message)}</p></div>`;}
    finally{planButton.disabled=false;planButton.innerHTML='Find bus journeys <span class="arrow">→</span>';}
  });
  fetch('/api/vehicles').then(r=>r.json()).then(d=>{
    const el=document.getElementById('live-status-text');
    if(el){el.textContent=d.status==='connected'?`${d.count} buses received`:d.status==='not_configured'?'Not connected':'Unavailable';el.className=d.status==='connected'?'good-text':'muted-text';}
    if(map && liveLayer && d.status==='connected') {
      (d.vehicles||[]).forEach(v=>{
        if(typeof v.lat!=='number'||typeof v.lon!=='number') return;
        const marker=L.circleMarker([v.lat,v.lon],{radius:5,color:'#fff',weight:2,fillColor:'#159b72',fillOpacity:1});
        marker.bindPopup(`<strong>Live bus</strong><br>${esc(v.route_id||'Route not supplied')}<br>${v.speed_kmh==null?'Speed not supplied':`${esc(v.speed_kmh)} km/h`}`);
        liveLayer.addLayer(marker);
      });
    }
  }).catch(()=>{const el=document.getElementById('live-status-text');if(el)el.textContent='Unavailable';});
})();
