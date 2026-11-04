// State of point edits that must outlive a redraw: polls rebuild the map and the
// excluded list every few seconds while a request may still be running.

export function createEditState() {
  return { inFlight: new Set(), error: "" };
}

function key(externalId, sequence) {
  return `${externalId}:${sequence}`;
}

export function isBusy(state, externalId, sequence) {
  return state.inFlight.has(key(externalId, sequence));
}

// False when the point already has a request running: the click is ignored.
export function beginEdit(state, externalId, sequence) {
  if (isBusy(state, externalId, sequence)) {
    return false;
  }
  state.inFlight.add(key(externalId, sequence));
  state.error = "";
  return true;
}

export function finishEdit(state, externalId, sequence) {
  state.inFlight.delete(key(externalId, sequence));
}

export function failEdit(state, externalId, sequence, message) {
  finishEdit(state, externalId, sequence);
  state.error = message;
}

export function clearEditError(state) {
  state.error = "";
}

export function followStatusText(notOnPatrol, editError) {
  return [notOnPatrol, editError].filter(Boolean).join(" · ");
}

// prev and next are { patrol, position, editable }, or prev is null when nothing is
// drawn. mergeRoutes only replaces changed patrols, so patrol identity is enough.
export function followedRouteChanged(prev, next) {
  if (prev === null) {
    return true;
  }
  if (prev.patrol !== next.patrol || prev.editable !== next.editable) {
    return true;
  }
  const a = prev.position;
  const b = next.position;
  if (a === null || b === null) {
    return a !== b;
  }
  return (
    a.lat !== b.lat ||
    a.lng !== b.lng ||
    a.date !== b.date ||
    a.sequence !== b.sequence ||
    a.dateApproximate !== b.dateApproximate
  );
}

// The point whose popup was open, if it is still on the route.
export function reopenSequence(openSequence, patrol) {
  if (openSequence === null || openSequence === undefined || patrol === null) {
    return null;
  }
  return patrol.points.some((point) => point.sequence === openSequence) ? openSequence : null;
}
