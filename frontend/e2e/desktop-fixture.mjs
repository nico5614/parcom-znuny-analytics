export async function setup(page, data) {
  page.on('pageerror', error => console.log('PAGE ERROR:', error.message))
  await page.addInitScript(data => {
    const calls = []
    const state = { connection: 'cached', busy: false, newData: false, revision: 0, capturedAt: data.capturedAt, hasCache: true, warning: '', lastSuccessfulConnection: '2026-10-08T10:23:45+02:00' }
    let period = data.periods['1W']
    let preferences = { theme: data.initialTheme || 'dark', reducedMotion: false }
    const automaticAgents = structuredClone(data.agents.registry)
    window.validation = { calls, failRefresh: false, refreshDelay: 0, exportDelay: 0 }
    const record = (name, args) => calls.push({ name, args })
    const ok = value => ({ ok: true, data: value })
    window.pywebview = { api: {
      getAppInfo: async () => ({ name: 'ParCom Analytics', version: '1.0.0', python: '3.14.8', renderer: 'Windows WebView2', packaged: false }),
      probe: async () => { window.dispatchEvent(new CustomEvent('parcom:desktop', { detail: { kind: 'probe', sequence: 1 } })); return { sequence: 1 } },
      confirmProbe: async () => true,
      getState: async () => ({ ...state }), getPeriod: async () => ({ ...period }),
      getPreferences: async () => preferences, setPreferences: async (theme, reducedMotion) => { preferences = { theme, reducedMotion }; return ok(null) },
      continueOffline: async () => ok({ username: 'Offline' }),
      login: async (username, password) => { record('login', [username, password.length]); if (username === 'network-error') return { ok: false, error: { kind: 'network', message: 'Znuny ist nicht erreichbar.' } }; if (username !== 'validation' || password !== 'validation') return { ok: false, error: { kind: 'authentication', message: 'Anmeldung fehlgeschlagen.' } }; state.connection = 'online'; return ok({ username }) },
      logout: async () => { record('logout', []); state.connection = 'cached'; return ok(null) },
      resolvePeriod: async selection => { record('resolvePeriod', [selection]); if (selection.preset) return ok(data.periods[selection.preset]); if (selection.start === data.custom.startInput && selection.end === data.custom.endInput) return ok(data.custom); return { ok: false, error: { kind: 'validation', message: 'Mindestens ein Tag ist erforderlich.' } } },
      refresh: async selection => { record('refresh', [selection]); await new Promise(resolve => setTimeout(resolve, window.validation.refreshDelay)); if (window.validation.failRefresh) return { ok: false, error: { kind: 'network', message: 'Die Znuny-Sitzung ist abgelaufen. Bitte erneut anmelden.' } }; period = selection.preset ? data.periods[selection.preset] : data.custom; state.revision++; state.newData = false; return ok({ ...state }) },
      checkChanges: async () => ({ ...state, newData: true }),
      getOverview: async () => { record('getOverview', []); return ok(data.overview) },
      getAnalysis: async (kpi, type, page) => { record('getAnalysis', [kpi, type, page]); return ok(data.analyses[kpi][type || 'all']) },
      getAgents: async (id, page) => { record('getAgents', [id, page]); return ok(data.agents) },
      setTeam: async selected => { record('setTeam', [selected]); data.agents.selected = selected; state.revision++; return ok({ ...state }) },
      setAgentDisplayName: async (id, name) => { record('setAgentDisplayName', [id, name]); const agent = data.agents.registry.find(agent => agent.id === id); agent.name = name; state.revision++; return ok({ ...agent }) },
      setAgentAbbreviation: async (id, code) => { record('setAgentAbbreviation', [id, code]); const agent = data.agents.registry.find(agent => agent.id === id); agent.code = code; state.revision++; return ok({ ...agent }) },
      resetAgentOverride: async id => { record('resetAgentOverride', [id]); const agent = data.agents.registry.find(agent => agent.id === id); Object.assign(agent, automaticAgents.find(agent => agent.id === id)); state.revision++; return ok({ ...agent }) },
      getTicketDetails: async id => { record('getTicketDetails', [id]); return ok(data.tickets[id]) },
      openTicket: async id => { record('openTicket', [id]); return ok(null) },
      getExportOptions: async () => Object.entries(data.analyses).map(([id, kinds]) => ({ id, label: kinds.all.title, types: kinds.all.types })),
      exportPdf: async (target, type) => { record('exportPdf', [target, type]); await new Promise(resolve => setTimeout(resolve, window.validation.exportDelay)); return ok({ cancelled: false, filename: 'synthetic-report.pdf' }) },
    } }
  }, structuredClone(data))
  await page.goto('/')
}
