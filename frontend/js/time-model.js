export function parseDate(dateStr) {
  if (!dateStr) {
    return null;
  }
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

export function datedPoints(patrol) {
  return patrol.points.filter((point) => point.date !== null && point.date !== undefined);
}

function pointsUpTo(patrol, targetDate) {
  const targetTime = targetDate.getTime();
  return datedPoints(patrol).filter((point) => parseDate(point.date).getTime() <= targetTime);
}

export function knownPosition(patrol, targetDate) {
  const dated = datedPoints(patrol);
  if (dated.length === 0) {
    return null;
  }
  if (targetDate.getTime() > parseDate(dated[dated.length - 1].date).getTime()) {
    return null;
  }

  const reached = pointsUpTo(patrol, targetDate);
  if (reached.length === 0) {
    return null;
  }

  const { lat, lng, date, sequence, date_approximate: dateApproximate = false } = reached[reached.length - 1];
  return { lat, lng, date, sequence, dateApproximate };
}

const LEG_DASH = "6 6";
const LEG_STYLES = {
  ok: { color: "#0077cc", dashArray: LEG_DASH },
  suspect: { color: "#e67e00", dashArray: LEG_DASH },
};

// Only legs with a believable water route are drawn; the rest have no line.
export function legStyle(status) {
  const style = LEG_STYLES[status];
  return style === undefined ? null : { ...style };
}

export function legMidpoint(leg, patrol) {
  const from = patrol.points.find((point) => point.sequence === leg.from_sequence);
  const to = patrol.points.find((point) => point.sequence === leg.to_sequence);
  if (from === undefined || to === undefined) {
    return null;
  }
  return [(from.lat + to.lat) / 2, (from.lng + to.lng) / 2];
}

// The leg that ends at the boat's current position, or null on the first point.
export function tailLeg(patrol, position) {
  const leg = (patrol.legs ?? []).find((candidate) => candidate.to_sequence === position.sequence);
  return leg === undefined ? null : leg;
}

export function activeBoatsOnDate(routes, targetDate) {
  const active = [];
  for (const patrol of routes) {
    const position = knownPosition(patrol, targetDate);
    if (position !== null) {
      active.push({
        boatSlug: patrol.boat_slug,
        boatNumber: patrol.boat_number,
        externalId: patrol.external_id,
        lat: position.lat,
        lng: position.lng,
        positionDate: position.date,
        dateApproximate: position.dateApproximate,
        sequence: position.sequence,
        patrol,
      });
    }
  }
  return active;
}

// Dates of every point of the patrol, excluded ones included: hiding a point must
// not change when the patrol is considered to have started.
function startDate(patrol) {
  const dates = [...patrol.points, ...(patrol.excluded_points ?? [])]
    .filter((point) => point.date !== null && point.date !== undefined)
    .map((point) => parseDate(point.date).getTime());
  return dates.length === 0 ? null : Math.min(...dates);
}

export function followView(patrols, targetDate) {
  const started = patrols
    .filter((patrol) => {
      const start = startDate(patrol);
      return start !== null && start <= targetDate.getTime();
    })
    .sort((a, b) => startDate(a) - startDate(b));

  if (started.length === 0) {
    return { patrol: null, position: null };
  }

  const patrol = started[started.length - 1];
  return { patrol, position: knownPosition(patrol, targetDate) };
}

export function positionLabel(boat) {
  const label = `${boat.boatNumber} — positie van ${boat.positionDate}`;
  return boat.dateApproximate ? `${label} (datum benaderd)` : label;
}

export function notOnPatrolMessage(boatNumber, targetDate) {
  return `${boatNumber} is op ${targetDate.toISOString().slice(0, 10)} niet op patrouille.`;
}

export function dateRange(routes) {
  let min = null;
  let max = null;
  for (const patrol of routes) {
    for (const point of datedPoints(patrol)) {
      const t = parseDate(point.date).getTime();
      if (min === null || t < min) {
        min = t;
      }
      if (max === null || t > max) {
        max = t;
      }
    }
  }
  if (min === null) {
    return null;
  }
  return { min: new Date(min), max: new Date(max) };
}

export function shouldFitRoute(fittedExternalId, patrol) {
  return patrol !== null && patrol.external_id !== fittedExternalId;
}
