const fieldNames = {
  length: 'Longueur', beam: 'Largeur', draft: 'Tirant d’eau', vessel: 'Nom du navire',
}

export async function api(path, method = 'GET', body) {
  let response
  try {
    response = await fetch('/api' + path, {
      method,
      ...(body && { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
    })
  } catch {
    throw new Error('Connexion à DockSlot impossible. Réessayez dans un instant.')
  }
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = data?.detail
    const validation = (Array.isArray(detail) ? detail : [])
      .map(({ loc }) => fieldNames[loc.at(-1)])
      .filter(Boolean)
    const message = typeof detail === 'string' ? detail
      : validation.length ? `Vérifiez la saisie · ${[...new Set(validation)].join(', ')}.`
        : 'Action impossible. Réessayez dans un instant.'
    throw new Error(message)
  }
  return data
}
