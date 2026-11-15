import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Anchor, ArrowRight, Building2, CalendarDays, ChevronDown, ClipboardList,
  FlaskConical, MapPin, RefreshCw, Ruler, Search, Ship, X,
} from 'lucide-react'
import { api } from './api'
import './style.css'

const initialSearch = { port: 'Marseille', length: '110', beam: '19', draft: '5' }
const statusLabels = { pending: 'En attente', accepted: 'Confirmée', rejected: 'Refusée' }
const dateFormat = new Intl.DateTimeFormat('fr-FR', {
  day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC',
})
const dateRange = ({ start_date, end_date }) =>
  dateFormat.formatRange(new Date(start_date), new Date(end_date))
const dimensionLabel = ({ length, beam, draft }) => `${length} × ${beam} m · tirant ${draft} m`

function SearchForm({ values, update, submit, busy, ports }) {
  return <form className="search-form" onSubmit={submit}>
    <div className="field">
      <label htmlFor="port">Port</label>
      <div className="port-input"><MapPin size={17} />
        <select id="port" value={values.port} onChange={e => update('port', e.target.value)}>
          {ports.map(port => <option key={port}>{port}</option>)}
        </select><ChevronDown size={15} />
      </div>
    </div>
    {[['length', 'Longueur'], ['beam', 'Largeur'], ['draft', 'Tirant d’eau']].map(([key, label]) =>
      <div className="field" key={key}>
        <label htmlFor={key}>{label}</label>
        <div className="number-input">
          <input id={key} type="number" min="0.01" max="1000" step="any" required
            value={values[key]} onChange={e => update(key, e.target.value)} />
          <span aria-hidden="true">m</span>
        </div>
      </div>)}
    <button className="btn primary search-button" disabled={busy}><Search size={18} /> Rechercher</button>
  </form>
}

function YardCard({ yard, onSelect, index }) {
  return <article className="yard-card">
    <div className={`yard-banner variant-${index % 3}`}>
      <div className="yard-icon"><Anchor size={23} /></div>
      <span className="capacity-tag">{yard.type}</span>
    </div>
    <div className="yard-content">
      <p className="location"><MapPin size={14} /> {yard.port}</p>
      <h3>{yard.name}</h3>
      <p className="description">{yard.description}</p>
      <p className="dimensions" title="Dimensions maximales"><Ruler size={16} /> {dimensionLabel(yard)}</p>
      <div className="slots">
        <p className="slots-title"><CalendarDays size={16} /> Créneaux disponibles</p>
        {yard.slots.length ? yard.slots.map(slot => <button className="slot" key={slot.id}
          onClick={() => onSelect(yard, slot)} aria-label={`Réserver à ${yard.name}, ${dateRange(slot)}`}>
          {dateRange(slot)} <ArrowRight size={16} />
        </button>) : <p className="muted text-sm">Aucun créneau disponible.</p>}
      </div>
    </div>
  </article>
}

function RequestDialog({ selection, close, save }) {
  const dialog = useRef(null)
  const [busy, setBusy] = useState(false)
  const [vessel, setVessel] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { dialog.current.showModal() }, [])
  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try { await save(vessel.trim()) }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }
  return <dialog ref={dialog} aria-labelledby="dialog-title" onCancel={event => {
    event.preventDefault()
    if (!busy) close()
  }}>
    <form onSubmit={submit}>
      <div className="section-heading">
        <h2 id="dialog-title">Demander ce créneau</h2>
        <button type="button" className="icon-button" aria-label="Fermer" onClick={close} disabled={busy}><X size={20} /></button>
      </div>
      <p className="mt-2 font-semibold">{selection.yard.name}</p>
      <p className="muted text-sm mt-1">{dateRange(selection.slot)} · {dimensionLabel(selection.criteria)}</p>
      <p className="muted text-sm mt-1">La date de fin correspond au jour de sortie de cale.</p>
      <div className="field mt-6">
        <label htmlFor="vessel">Nom du navire</label>
        <input id="vessel" value={vessel} onChange={e => setVessel(e.target.value)}
          placeholder="Ex. Horizon Atlantique" required minLength={2} maxLength={80} autoFocus />
      </div>
      {error && <p role="alert" className="message error mt-4">{error}</p>}
      <button className="btn primary mt-6 w-full" disabled={busy}>{busy ? 'Envoi…' : 'Envoyer la demande'} <ArrowRight size={17} /></button>
    </form>
  </dialog>
}

function BookingPanel({ isYard, yards, yardId, setYardId, bookings, reload, decide, busy, decisionBusy }) {
  const counters = Object.keys(statusLabels).map(state => ({
    state, count: bookings.filter(item => item.status === state).length,
  }))
  return <>
    <div className="section-heading wrap">
      <div><h2>{isYard ? 'Demandes du chantier' : 'Mes réservations'}</h2>
        <p className="muted mt-1">{isYard ? 'Consultez et traitez les demandes de carénage.' : 'Suivez les décisions des chantiers sur vos demandes.'}</p></div>
      <button className="btn secondary" type="button" onClick={reload} disabled={busy}><RefreshCw size={16} /> Actualiser</button>
    </div>
    {isYard && <div className="field yard-select mt-5">
      <label htmlFor="yard">Chantier naval</label>
      <select id="yard" disabled={decisionBusy} value={yardId} onChange={e => setYardId(e.target.value)}>
        {yards.map(yard => <option key={yard.id} value={yard.id}>{yard.name} · {yard.port}</option>)}
      </select>
    </div>}
    <div className="metrics" aria-label="Bilan des demandes">{counters.map(({ state, count }) =>
      <div key={state} className="metric"><span className={`status ${state}`}>{statusLabels[state]}</span><strong>{count}</strong></div>)}
    </div>
    {bookings.length ? <div className="table-scroll" tabIndex={0} role="region" aria-label="Tableau des réservations">
      <table><thead><tr><th scope="col">Navire</th><th scope="col">Chantier</th><th scope="col">Créneau</th>
        <th scope="col">Statut</th>{isYard && <th scope="col">Décision</th>}</tr></thead>
        <tbody>{bookings.map(booking => <tr key={booking.id}>
          <td><strong>{booking.vessel}</strong><small>{dimensionLabel(booking)}</small></td>
          <td>{booking.yard_name}<small>{booking.port}</small></td>
          <td>{dateRange(booking)}</td><td><span className={`status ${booking.status}`}>{statusLabels[booking.status]}</span></td>
          {isYard && <td>{booking.status === 'pending' && <div className="actions">
            <button className="btn primary compact" disabled={decisionBusy || busy}
              onClick={() => decide(booking, 'accepted')}>Accepter</button>
            <button className="btn secondary compact" disabled={decisionBusy || busy}
              onClick={() => decide(booking, 'rejected')}>Refuser</button>
          </div>}</td>}
        </tr>)}</tbody></table>
    </div> : <div className="empty"><ClipboardList size={27} /><p>{busy ? 'Chargement des demandes…' : 'Aucune demande pour le moment.'}</p></div>}
  </>
}

function App() {
  const [tab, setTab] = useState('search')
  const [values, setValues] = useState(initialSearch)
  const [criteria, setCriteria] = useState(initialSearch)
  const [yards, setYards] = useState([])
  const [yardId, setYardId] = useState('1')
  const [matches, setMatches] = useState([])
  const [bookingList, setBookingList] = useState({ scope: '', items: [] })
  const [selection, setSelection] = useState(null)
  const [searchBusy, setSearchBusy] = useState(true)
  const [listBusy, setListBusy] = useState(false)
  const [decisionBusy, setDecisionBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  const isYard = tab === 'yard'
  const scope = isYard ? yardId : 'all'
  const bookingRequest = useRef(0)

  useEffect(() => {
    api('/yards').then(setYards).catch(err => setNotice({ error: true, text: err.message }))
  }, [])

  useEffect(() => {
    if (tab === 'search') {
      find(criteria)
    } else {
      loadBookings(scope)
    }
  }, [tab, scope])

  async function find(query) {
    setSearchBusy(true)
    try {
      const results = await api('/search?' + new URLSearchParams(query))
      setMatches(results)
      setCriteria({ ...query })
    } catch (err) { setNotice({ error: true, text: err.message }) }
    finally { setSearchBusy(false) }
  }

  async function loadBookings(listScope) {
    const requestId = ++bookingRequest.current
    setListBusy(true)
    try {
      const items = await api('/bookings' + (listScope === 'all' ? '' : '?yard_id=' + listScope))
      if (bookingRequest.current === requestId) setBookingList({ scope: listScope, items })
    } catch (err) {
      if (bookingRequest.current === requestId) setNotice({ error: true, text: err.message })
    } finally {
      if (bookingRequest.current === requestId) setListBusy(false)
    }
  }

  function navigate(next) {
    if (next === tab) return
    bookingRequest.current++
    setNotice(null)
    setTab(next)
  }

  async function save(vessel) {
    const { length, beam, draft } = selection.criteria
    const booking = await api('/bookings', 'POST', {
      vessel, slot_id: selection.slot.id, length: Number(length), beam: Number(beam), draft: Number(draft),
    })
    setSelection(null)
    setYardId(String(booking.yard_id))
    setNotice({ text: `Demande envoyée pour ${booking.vessel}.` })
    setTab('bookings')
  }

  async function decide(booking, status) {
    setDecisionBusy(true)
    setNotice(null)
    try {
      await api(`/yards/${booking.yard_id}/bookings/${booking.id}`, 'PATCH', { status })
      setNotice({ text: `Demande ${statusLabels[status].toLowerCase()} pour ${booking.vessel}.` })
    } catch (err) { setNotice({ error: true, text: err.message }) }
    finally {
      await loadBookings(scope)
      setDecisionBusy(false)
    }
  }

  return <>
    <header className="topbar">
      <div className="shell navigation">
        <button className="brand" disabled={decisionBusy} onClick={() => navigate('search')}><span><Anchor size={22} /></span> DockSlot</button>
        <nav aria-label="Navigation principale">
          {[['search', Search, 'Rechercher'], ['bookings', ClipboardList, 'Mes réservations'], ['yard', Building2, 'Espace chantier']]
            .map(([key, Icon, label]) => <button key={key} onClick={() => navigate(key)}
              aria-current={tab === key ? 'page' : undefined} disabled={decisionBusy}><Icon size={17} />{label}</button>)}
        </nav>
        <span className="demo"><FlaskConical size={14} /> Démo · données fictives</span>
      </div>
    </header>
    <main className="shell">
      <section className="hero">
        <div className="hero-inner">
          <span className="hero-label"><Ship size={16} /> {isYard ? 'Mode chantier simulé' : 'Mode exploitant simulé'}</span>
          <h1>{tab === 'search' ? 'Planifiez votre carénage' : isYard ? 'Espace chantier' : 'Suivi des réservations'}</h1>
          <p>{tab === 'search' ? 'Trouvez un chantier adapté à votre navire et demandez un créneau disponible.'
            : isYard ? 'Gérez les demandes de réservation de votre chantier.' : 'Retrouvez vos demandes et leur statut.'}</p>
        </div>
      </section>
      {tab === 'search' && <SearchForm values={values} ports={yards.length ? [...new Set(yards.map(y => y.port))] : ['Marseille']}
        update={(key, value) => setValues({ ...values, [key]: value })}
        submit={e => { e.preventDefault(); setNotice(null); find(values) }} busy={searchBusy} />}
      {notice && <p className={`message ${notice.error ? 'error' : 'success'}`} role={notice.error ? 'alert' : 'status'}>{notice.text}</p>}
      <section className="panel" aria-label={tab === 'search' ? 'Résultats' : 'Réservations'}>
        {tab === 'search' ? <>
          <div className="section-heading wrap">
            <div><h2>Chantiers compatibles</h2><p className="muted mt-1">{criteria.port} · {dimensionLabel(criteria)}</p></div>
            <span className="count">{matches.length} chantier{matches.length === 1 ? '' : 's'}</span>
          </div>
          <div className="yard-grid" aria-busy={searchBusy}>{matches.map((yard, index) => <YardCard key={yard.id}
            yard={yard} index={index} onSelect={(yard, slot) => setSelection({ yard, slot, criteria })} />)}</div>
          {!matches.length && <div className="empty"><Ship size={27} /><p>{searchBusy ? 'Recherche en cours…' : 'Aucun chantier ne correspond à ces dimensions dans ce port.'}</p></div>}
        </> : <BookingPanel isYard={isYard} yards={yards} yardId={yardId}
          setYardId={id => { setNotice(null); setYardId(id) }} bookings={bookingList.scope === scope ? bookingList.items : []}
          reload={() => { setNotice(null); loadBookings(scope) }} decide={decide} busy={listBusy} decisionBusy={decisionBusy} />}
      </section>
    </main>
    <footer className="shell"><span><Anchor size={15} /> DockSlot</span><span>Prototype · chantiers et disponibilités fictifs</span></footer>
    {selection && <RequestDialog selection={selection} close={() => setSelection(null)} save={save} />}
  </>
}

createRoot(document.getElementById('root')).render(<App />)
