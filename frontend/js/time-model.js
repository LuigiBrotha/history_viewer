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

  const { lat, lng, date } = reached[reached.length - 1];
  return { lat, lng, date };
}

export function lastLeg(patrol, targetDate) {
  const reached = pointsUpTo(patrol, targetDate);
  if (reached.length < 2) {
    return null;
  }
  return reached.slice(-2).map((point) => [point.lat, point.lng]);
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
        tail: lastLeg(patrol, targetDate),
        patrol,
      });
    }
  }
  return active;
}

export function followView(patrols, targetDate) {
  const started = patrols
    .filter((patrol) => pointsUpTo(patrol, targetDate).length > 0)
    .sort((a, b) => parseDate(datedPoints(a)[0].date) - parseDate(datedPoints(b)[0].date));

  if (started.length === 0) {
    return { patrol: null, position: null };
  }

  const patrol = started[started.length - 1];
  return { patrol, position: knownPosition(patrol, targetDate) };
}

export function positionLabel(boat) {
  return `${boat.boatNumber} — positie van ${boat.positionDate}`;
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
