// Illustrated shaadi scenes for post backgrounds, drawn as SVG from simple
// geometry in the spirit of the Shaadi Planner Pro invitation art. Each scene
// fills a 1080x1350 canvas and keeps a calm area where the post's text sits.
// Output is deterministic for a given seed, so a re-render looks the same.
(function () {
  const W = 1080, H = 1350
  const r2 = n => Math.round(n * 100) / 100

  function rng(seed) {
    let a = (seed >>> 0) || 1
    return () => {
      a = (a + 0x6D2B79F5) >>> 0
      let t = a
      t = Math.imul(t ^ (t >>> 15), t | 1)
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296
    }
  }
  const ring = (count, offset, draw) => Array.from({ length: count }, (_, i) => draw(offset + (360 / count) * i, i)).join('')
  let uid = 0
  const id = name => `s${++uid}-${name}`

  const C = {
    night: '#2a0a18', wine: '#5a1733', maroon: '#762747',
    gold: '#e2a64a', goldLight: '#f6d58b', goldDeep: '#a9682b',
    f1: '#f59e0b', f2: '#f97316', f3: '#fbbf24', core: '#9a3412',
    leaf: '#3f7d3f', leaf2: '#5b9a4b', leafDeep: '#24502a',
    cream: '#fff8e9', henna: '#7a2e0e', skin: '#f2d3b3', clay: '#b4532a', clayDeep: '#7c2d12',
  }

  const blur = (name, sd) => `<filter id="${name}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="${sd}"/></filter>`

  // A marigold head: rings of rounded petals around a deep core.
  function bloom(x, y, r, alt) {
    const [a, b, c] = alt ? [C.f3, C.f2, C.f1] : [C.f1, C.f2, C.f3]
    return `<g transform="translate(${r2(x)} ${r2(y)})">`
      + ring(18, 0, an => `<ellipse cy="${r2(-r * .66)}" rx="${r2(r * .2)}" ry="${r2(r * .34)}" fill="${a}" transform="rotate(${r2(an)})"/>`)
      + ring(14, 12, an => `<ellipse cy="${r2(-r * .46)}" rx="${r2(r * .19)}" ry="${r2(r * .28)}" fill="${b}" transform="rotate(${r2(an)})"/>`)
      + ring(10, 4, an => `<ellipse cy="${r2(-r * .26)}" rx="${r2(r * .16)}" ry="${r2(r * .22)}" fill="${c}" transform="rotate(${r2(an)})"/>`)
      + `<circle r="${r2(r * .16)}" fill="${C.core}"/></g>`
  }

  // Out-of-focus lights: the "blurred shaadi" backdrop most scenes sit on.
  function bokeh(rand, { count = 70, top = 0, bottom = H, colors = [C.gold, C.goldLight, '#f9a8d4', '#fde68a', '#fb923c'], strength = 1 } = {}) {
    const soft = id('soft'), softer = id('softer')
    let dots = ''
    for (let i = 0; i < count; i++) {
      const r = 12 + rand() * 62
      const f = r > 40 ? softer : soft
      dots += `<circle cx="${r2(rand() * W)}" cy="${r2(top + rand() * (bottom - top))}" r="${r2(r)}" fill="${colors[i % colors.length]}" opacity="${r2((.12 + rand() * .45) * strength)}" filter="url(#${f})"/>`
    }
    return `<defs>${blur(soft, 6)}${blur(softer, 16)}</defs>${dots}`
  }

  function backdrop(top, bottom, glowAt = .78) {
    const g = id('bg'), glow = id('glow')
    return `<defs><linearGradient id="${g}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${top}"/><stop offset="1" stop-color="${bottom}"/></linearGradient>
      <radialGradient id="${glow}" cx="50%" cy="${glowAt * 100}%" r="70%"><stop offset="0" stop-color="${C.gold}" stop-opacity=".35"/><stop offset="1" stop-color="${C.gold}" stop-opacity="0"/></radialGradient></defs>
      <rect width="${W}" height="${H}" fill="url(#${g})"/><rect width="${W}" height="${H}" fill="url(#${glow})"/>`
  }

  // A string of marigolds hanging from (x, y).
  function ladi(x, y, length, r, sway = 0) {
    let s = `<path d="M${x} ${y}V${y + length}" stroke="${C.goldDeep}" stroke-width="1.5"/>`
    const step = r * 1.7
    for (let i = 0, yy = y + r; yy < y + length; i++, yy += step) s += bloom(x + Math.sin(i * .9) * sway, yy, r, i % 2)
    return s
  }

  // Mango leaves and marigolds strung across the top.
  function toranStrip(y, tiles, tile) {
    const leaf = 'M0 0C7 7 8 24 0 38C-8 24-7 7 0 0Z'
    let s = `<path d="M0 ${y + 5}${Array.from({ length: tiles }, () => `q${tile / 2} ${tile * .12} ${tile} 0`).join('')}" fill="none" stroke="${C.goldDeep}" stroke-width="3"/>`
    for (let i = 0; i < tiles; i++) {
      const x = i * tile, k = tile / 60
      s += `<g transform="translate(${x} ${y}) scale(${k})">
        <path d="${leaf}" transform="translate(15 7) rotate(8) scale(1.6)" fill="${C.leaf}"/>
        <path d="M0 2V34" transform="translate(15 7) rotate(8) scale(1.6)" stroke="${C.leafDeep}" stroke-width="1" opacity=".7"/>
        <path d="${leaf}" transform="translate(45 7) rotate(-8) scale(1.6)" fill="${C.leaf2}"/>
        <path d="M0 2V34" transform="translate(45 7) rotate(-8) scale(1.6)" stroke="${C.leafDeep}" stroke-width="1" opacity=".7"/>
      </g>${bloom(x + tile / 2, y + 16 * k, 13 * k)}${bloom(x, y + 10 * k, 8 * k, true)}`
    }
    return s
  }

  const scenes = {}

  // Night bokeh with a soft glow; the plainest backdrop for longer text.
  scenes.lights = (rand) => backdrop(C.night, C.wine, .5) + bokeh(rand, { count: 90 })

  // Marigold toran across the top, garlands down the sides, lights behind.
  scenes.toran = (rand) => {
    const far = id('far')
    let back = ''
    for (let i = 0; i < 9; i++) back += ladi(60 + rand() * 960, -20, 300 + rand() * 500, 16 + rand() * 8, 4)
    return backdrop(C.night, C.maroon, .55) + bokeh(rand, { count: 50, strength: .8 })
      + `<defs>${blur(far, 7)}</defs><g filter="url(#${far})" opacity=".45">${back}</g>`
      + ladi(70, 40, 1150, 26, 6) + ladi(150, 40, 820, 22, 5) + ladi(1010, 40, 1150, 26, 6) + ladi(930, 40, 820, 22, 5)
      + toranStrip(0, 9, 120)
  }

  // A row of clay diyas glowing along the bottom edge.
  scenes.diyas = (rand) => {
    const flame = id('flame'), halo = id('halo'), clay = id('clay'), ledge = id('ledge')
    const defs = `<defs>
      <radialGradient id="${flame}" cx="50%" cy="72%" r="70%"><stop offset="0" stop-color="#fffbe6"/><stop offset=".35" stop-color="#ffe07a"/><stop offset=".75" stop-color="#ff9a2e"/><stop offset="1" stop-color="#e2541c"/></radialGradient>
      <radialGradient id="${halo}"><stop offset="0" stop-color="#ffd27a" stop-opacity=".75"/><stop offset="1" stop-color="#ff9a2e" stop-opacity="0"/></radialGradient>
      <linearGradient id="${clay}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#d9733f"/><stop offset=".6" stop-color="${C.clay}"/><stop offset="1" stop-color="${C.clayDeep}"/></linearGradient>
      <linearGradient id="${ledge}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3b1020"/><stop offset="1" stop-color="#1a0610"/></linearGradient></defs>`
    const diya = (x, y, s) => `<g transform="translate(${x} ${y}) scale(${s})">
      <circle cy="-48" r="95" fill="url(#${halo})"/>
      <path d="M-62 0Q-58 34 0 38Q58 34 62 0L84 -10Q60 -4 40 -2H-40Q-60 -4 -62 0Z" fill="url(#${clay})"/>
      <ellipse cx="0" cy="-1" rx="58" ry="9" fill="${C.clayDeep}"/>
      <ellipse cx="0" cy="-3" rx="50" ry="6" fill="#4a1a0a"/>
      <path d="M-44 14Q0 26 44 14" stroke="#f0a070" stroke-width="2.4" fill="none" opacity=".55"/>
      <g fill="none" stroke="#f6c27a" stroke-width="2" opacity=".6"><circle cx="-26" cy="20" r="3"/><circle cx="0" cy="24" r="3"/><circle cx="26" cy="20" r="3"/></g>
      <path d="M70 -34C80 -20 82 -10 72 -4C62 -10 62 -20 70 -34Z" fill="url(#${flame})"/>
      <path d="M72 -60C86 -36 86 -16 72 -6C58 -16 58 -36 72 -60Z" fill="url(#${flame})" opacity=".95"/>
      <ellipse cx="72" cy="-18" rx="3" ry="7" fill="#fff8de"/></g>`
    let petals = ''
    for (let i = 0; i < 26; i++) {
      const x = rand() * W, y = 1110 + rand() * 70
      petals += `<ellipse cx="${r2(x)}" cy="${r2(y)}" rx="${r2(6 + rand() * 6)}" ry="${r2(3 + rand() * 3)}" fill="${[C.f1, C.f2, C.f3, '#e11d48'][i % 4]}" transform="rotate(${r2(rand() * 180)} ${r2(x)} ${r2(y)})" opacity=".9"/>`
    }
    return backdrop(C.night, '#4a1028', .85) + bokeh(rand, { count: 70, bottom: 900, strength: .9 }) + defs
      + `<path d="M0 1030Q540 995 1080 1030V1350H0Z" fill="url(#${ledge})"/>`
      + diya(150, 1065, 1.45) + diya(470, 1045, 1.8) + diya(830, 1065, 1.45)
      + bloom(70, 1130, 26) + bloom(1010, 1142, 24, true) + bloom(560, 1150, 20) + petals
  }

  // A henna mandala, like the centre of a mehendi design, on warm skin tones.
  scenes.mehendi = (rand) => {
    const bg = id('mbg'), far = id('mfar')
    const ink = C.henna
    const mandala = (s, sw) => `<g fill="none" stroke="${ink}" stroke-width="${sw}" stroke-linecap="round">
      <circle r="${18 * s}"/><circle r="${30 * s}" stroke-dasharray="${2 * s} ${6 * s}"/>
      ${ring(12, 0, a => `<path d="M0 ${-34 * s}C${14 * s} ${-50 * s} ${14 * s} ${-74 * s} 0 ${-90 * s}C${-14 * s} ${-74 * s} ${-14 * s} ${-50 * s} 0 ${-34 * s}Z" transform="rotate(${a})"/><path d="M0 ${-44 * s}V${-80 * s}" transform="rotate(${a})" stroke-width="${sw * .6}"/>`)}
      <circle r="${100 * s}"/>
      ${ring(24, 7.5, a => `<path d="M0 ${-104 * s}C${10 * s} ${-118 * s} ${8 * s} ${-136 * s} 0 ${-146 * s}C${-8 * s} ${-136 * s} ${-10 * s} ${-118 * s} 0 ${-104 * s}Z" transform="rotate(${a})"/>`)}
      <circle r="${154 * s}" stroke-dasharray="${1 * s} ${9 * s}" stroke-width="${sw * 1.8}"/>
      ${ring(16, 0, a => `<path d="M0 ${-162 * s}C${30 * s} ${-176 * s} ${30 * s} ${-214 * s} ${8 * s} ${-226 * s}C${-6 * s} ${-232 * s} ${-18 * s} ${-220 * s} ${-10 * s} ${-208 * s}C${-4 * s} ${-200 * s} ${8 * s} ${-204 * s} ${8 * s} ${-212 * s}" transform="rotate(${a})"/>`)}
      <circle r="${240 * s}"/>
      ${ring(48, 0, a => `<circle cy="${-250 * s}" r="${3 * s}" fill="${ink}" stroke="none" transform="rotate(${a})"/>`)}
      ${ring(32, 5.6, a => `<path d="M${-9 * s} ${-262 * s}Q0 ${-290 * s} ${9 * s} ${-262 * s}" transform="rotate(${a})"/>`)}
    </g>`
    return `<defs><radialGradient id="${bg}" cx="50%" cy="45%" r="75%"><stop offset="0" stop-color="#f7e1c6"/><stop offset="1" stop-color="#d9a77c"/></radialGradient>${blur(far, 5)}</defs>
      <rect width="${W}" height="${H}" fill="url(#${bg})"/>
      <g filter="url(#${far})" opacity=".35"><g transform="translate(40 120)">${mandala(.9, 3)}</g><g transform="translate(1060 1260)">${mandala(1.1, 3)}</g><g transform="translate(980 80)">${mandala(.5, 2.5)}</g></g>
      <g transform="translate(540 960)" opacity=".92">${mandala(1.05, 3)}</g>`
  }

  // A sikku kolam: one closed line weaving between dots and looping around
  // the outer ones, built as a mirror curve. Ported from the Temple & Kolam
  // invitation template (web/src/invitation/templates/temple-kolam/art.tsx).
  function buildKolam(cols, rows, gap, mirror) {
    const maxA = 2 * cols - 2, maxB = 2 * rows - 2
    const valid = (a, b) => a >= 0 && a <= maxA && b >= 0 && b <= maxB
    const inner = (a, b) => a > 0 && a < maxA && b > 0 && b < maxB
    const wall = (a, b) => inner(a, b) ? mirror(a, b) : 0
    const seen = new Set()
    const key = (a, b, dx, dy) => a + ',' + b + ',' + dx * dy
    const f = n => r2(n * gap / 2)
    const paths = []
    for (let b = 0; b <= maxB; b++) for (let a = 0; a <= maxA; a++) {
      if ((a + b) % 2 === 0 || wall(a, b)) continue
      for (const [dx0, dy0] of [[1, 1], [1, -1]]) {
        if (seen.has(key(a, b, dx0, dy0))) continue
        let p = [a, b], d = [dx0, dy0], start = [a, b], path = ''
        for (let guard = 0; guard < 4000; guard++) {
          seen.add(key(p[0], p[1], d[0], d[1]))
          const c = [p[0] + d[0], p[1] + d[1]]
          const nd = [...d]
          let next
          if (valid(c[0], c[1])) {
            const m = wall(c[0], c[1])
            if (m) {
              if ((m === 1) === (c[0] % 2 === 1)) nd[1] = -nd[1]; else nd[0] = -nd[0]
              const end = [c[0] + nd[0] / 2, c[1] + nd[1] / 2]
              path += `M${f(start[0])} ${f(start[1])}L${f((p[0] + c[0]) / 2)} ${f((p[1] + c[1]) / 2)}Q${f(c[0])} ${f(c[1])} ${f(end[0])} ${f(end[1])}`
              start = end
            } else {
              path += `M${f(start[0])} ${f(start[1])}L${f(c[0])} ${f(c[1])}`
              start = c
            }
            next = c
          } else {
            const xOut = c[0] < 0 || c[0] > maxA
            const q = p[0] % 2 ? [p[0] + d[0], p[1]] : [p[0], p[1] + d[1]]
            if (xOut) nd[0] = -nd[0]; else nd[1] = -nd[1]
            let off = xOut ? [0, nd[1]] : [nd[0], 0]
            next = [q[0] + off[0], q[1] + off[1]]
            let k = 1.9
            if (!valid(next[0], next[1])) {
              k = 2.7
              if (xOut) { nd[1] = -nd[1]; off = [nd[0], 0] } else { nd[0] = -nd[0]; off = [0, nd[1]] }
              next = [q[0] + off[0], q[1] + off[1]]
            }
            path += `M${f(start[0])} ${f(start[1])}C${f(p[0] + d[0] * k)} ${f(p[1] + d[1] * k)} ${f(next[0] - nd[0] * k)} ${f(next[1] - nd[1] * k)} ${f(next[0])} ${f(next[1])}`
            start = next
          }
          p = next; d = nd
          if (p[0] === a && p[1] === b && seen.has(key(a, b, d[0], d[1]))) break
        }
        paths.push(path)
      }
    }
    const dots = []
    for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) dots.push([x * gap, y * gap])
    return { paths, dots, size: [(cols - 1) * gap, (rows - 1) * gap] }
  }
  const ringDistance = (a, b, centre) => Math.abs(a - centre) + Math.abs(b - centre)

  function kolamArt(shape, x, y, stroke, width, dotR) {
    const [w, h] = shape.size
    return `<g transform="translate(${r2(x - w / 2)} ${r2(y - h / 2)})">
      <g fill="none" stroke="${stroke}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round">${shape.paths.map(d => `<path d="${d}"/>`).join('')}</g>
      ${shape.dots.map(([dx, dy]) => `<circle cx="${dx}" cy="${dy}" r="${dotR}" fill="${stroke}"/>`).join('')}</g>`
  }

  // A white kolam on a red-oxide floor, with smaller ones fading into the dark.
  scenes.kolam = (rand) => {
    const floor = id('floor'), far = id('kfar')
    const big = buildKolam(7, 7, 74, (a, b) => [1, 5].includes(ringDistance(a, b, 6)) ? 2 : 0)
    const small = buildKolam(5, 5, 60, (a, b) => ringDistance(a, b, 4) === 1 ? 2 : 0)
    return `<defs><radialGradient id="${floor}" cx="50%" cy="78%" r="85%"><stop offset="0" stop-color="#b24a32"/><stop offset="1" stop-color="#5a1c12"/></radialGradient>${blur(far, 4)}</defs>
      <rect width="${W}" height="${H}" fill="url(#${floor})"/>`
      + bokeh(rand, { count: 30, bottom: 500, colors: [C.goldLight, '#fde68a'], strength: .6 })
      + `<g filter="url(#${far})" opacity=".35">${kolamArt(small, 110, 1130, C.cream, 4, 4)}${kolamArt(small, 980, 700, C.cream, 4, 4)}</g>`
      + kolamArt(big, 540, 960, C.cream, 5.5, 5.5)
      + bloom(540, 960, 34) + bloom(250, 1160, 24, true) + bloom(830, 1160, 24)
  }

  // A dhol with zig-zag rope lacing, a marigold garland and its two sticks.
  scenes.dhol = (rand) => {
    const body = id('dbody'), head = id('dhead'), rim = id('drim')
    const defs = `<defs>
      <linearGradient id="${body}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b0455c"/><stop offset=".45" stop-color="${C.maroon}"/><stop offset="1" stop-color="#3f0d22"/></linearGradient>
      <linearGradient id="${rim}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${C.goldLight}"/><stop offset=".5" stop-color="${C.gold}"/><stop offset="1" stop-color="${C.goldDeep}"/></linearGradient>
      <radialGradient id="${head}" cx="42%" cy="38%"><stop offset="0" stop-color="#fffaf0"/><stop offset="1" stop-color="#dcc39a"/></radialGradient></defs>`
    const L = 300, R = 160
    let zig = `M${-L} ${-R + 16}`
    const n = 14
    for (let i = 1; i <= n; i++) zig += `L${r2(-L + (2 * L) * i / n)} ${i % 2 ? R - 16 : -R + 16}`
    let garland = ''
    for (let i = 0; i <= 14; i++) {
      const t = i / 14, x = -L + 40 + t * (2 * L - 80), y = -R + 10 + 70 * Math.sin(Math.PI * t)
      garland += bloom(x, y, 24, i % 2)
    }
    const drum = `<g transform="translate(540 1000) rotate(-8)">
      <ellipse cx="0" cy="${R + 40}" rx="${L + 40}" ry="30" fill="#000" opacity=".35"/>
      <rect x="${-L}" y="${-R}" width="${2 * L}" height="${2 * R}" fill="url(#${body})"/>
      <path d="M${-L} ${-R}Q0 ${-R - 26} ${L} ${-R}" fill="none" stroke="#c45a72" stroke-width="3" opacity=".6"/>
      <path d="${zig}" fill="none" stroke="${C.cream}" stroke-width="7" stroke-linejoin="round" opacity=".95"/>
      <rect x="${-L}" y="-14" width="${2 * L}" height="28" fill="url(#${rim})" opacity=".95"/>
      ${Array.from({ length: 9 }, (_, i) => `<circle cx="${-L + 60 + i * 60}" cy="0" r="7" fill="${C.goldDeep}"/>`).join('')}
      <ellipse cx="${-L}" cy="0" rx="62" ry="${R + 8}" fill="url(#${rim})"/><ellipse cx="${-L}" cy="0" rx="50" ry="${R - 6}" fill="url(#${head})"/>
      <ellipse cx="${L}" cy="0" rx="62" ry="${R + 8}" fill="url(#${rim})"/><ellipse cx="${L + 4}" cy="0" rx="50" ry="${R - 6}" fill="url(#${head})"/>
      <ellipse cx="${L + 4}" cy="0" rx="18" ry="58" fill="#3b2a1a" opacity=".28"/>
      ${garland}
    </g>`
    const sticks = `<g stroke-linecap="round" fill="none">
      <path d="M770 1290Q860 1040 1010 860" stroke="#6b4423" stroke-width="20"/><path d="M770 1290Q860 1040 1010 860" stroke="#a87443" stroke-width="10"/>
      <path d="M200 1300L330 1150" stroke="#8b5a2b" stroke-width="9"/></g>`
    return backdrop(C.night, C.wine, .62) + bokeh(rand, { count: 85, bottom: 820 }) + defs + drum + sticks
  }

  window.renderScene = (name, seed) => {
    const draw = scenes[name]
    if (!draw) throw new Error('unknown scene ' + name)
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" preserveAspectRatio="xMidYMid slice">${draw(rng(seed || 1))}</svg>`
  }
  window.sceneNames = Object.keys(scenes)
})()
