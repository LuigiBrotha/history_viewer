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

export function interpolatePosition(patrol, targetDate) {
  const dated = datedPoints(patrol);
  if (dated.length === 0) {
    return null;
  }

  const targetTime = targetDate.getTime();
  const firstTime = parseDate(dated[0].date).getTime();
  const lastTime = parseDate(dated[dated.length - 1].date).getTime();

  if (targetTime < firstTime || targetTime > lastTime) {
    return null;
  }

  for (let i = 0; i < dated.length - 1; i++) {
    const t0 = parseDate(dated[i].date).getTime();
    const t1 = parseDate(dated[i + 1].date).getTime();

    if (targetTime === t0) {
      return { lat: dated[i].lat, lng: dated[i].lng };
    }
    if (targetTime === t1) {
      return { lat: dated[i + 1].lat, lng: dated[i + 1].lng };
    }
    if (targetTime > t0 && targetTime < t1) {
      const fraction = (targetTime - t0) / (t1 - t0);
      return {
        lat: dated[i].lat + (dated[i + 1].lat - dated[i].lat) * fraction,
        lng: dated[i].lng + (dated[i + 1].lng - dated[i].lng) * fraction,
      };
    }
  }

  // dated.length === 1: firstTime === lastTime === targetTime, already checked above.
  return { lat: dated[0].lat, lng: dated[0].lng };
}

export function activeBoatsOnDate(routes, targetDate) {
  const active = [];
  for (const patrol of routes) {
    const position = interpolatePosition(patrol, targetDate);
    if (position !== null) {
      active.push({
        boatSlug: patrol.boat_slug,
        boatNumber: patrol.boat_number,
        externalId: patrol.external_id,
        lat: position.lat,
        lng: position.lng,
        patrol,
      });
    }
  }
  return active;
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
