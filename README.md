## SOS2526-11
[![Known Vulnerabilities](https://snyk.io/test/github/gti-sos/sos2526-11/badge.svg)](https://snyk.io/test/github/gti-sos/sos2526-11)
[![Codecov Coverage](https://codecov.io/gh/gti-sos/sos2526-11/graph/badge.svg)](https://codecov.io/gh/gti-sos/sos2526-11)

- **Team**
  - [Tomás Gutiérrez García](https://github.com/tomgutgar)
  - [Miguel Ridao Gallardo](https://github.com/Ridawo)
  - [José Fernández Montero](https://github.com/josfermon)
- **Project description**: Our project analyzes global traffic accident data to study the relationship between fatality rates, alcohol consumption, and literacy levels, determining how these variables influence road safety outcomes across different world regions.
- **Repository**: [gti-sos/SOS2526-11](https://github.com/gti-sos/SOS2526-11)
- **URL:** https://sos2526-11.onrender.com
- **APIs**:
  - https://sos2526-11.onrender.com/api/v1/alcohol-consumptions-per-capita/docs (developed by Miguel Ridao Gallardo)
  - https://sos2526-11.onrender.com/api/v1/literacy-rates/docs (developed by Tomás Gutiérrez García)
  - https://sos2526-11.onrender.com/api/v1/road-fatalities/docs (developed by José Fernández Montero)
  - https://sos2526-11.onrender.com/api/v2/alcohol-consumptions-per-capita/docs (developed by Miguel Ridao Gallardo - v2)
  - https://sos2526-11.onrender.com/api/v2/literacy-rates/docs (developed by Tomás Gutiérrez García - v2)
  - https://sos2526-11.onrender.com/api/v2/road-fatalities/docs (developed by José Fernández Montero - v2).

## About this fork

This repository is a fork of [gti-sos/SOS2526-11](https://github.com/gti-sos/SOS2526-11), the project above, built last year for the course SOS by Tomás, José and me. All credit for the original application goes to the three of us, as listed in the Team section — this fork doesn't change that.

I'm using it for a university security engineering assignment (PAI-3): a black-box web pentest against my own local copy, followed by fixing what I found. On top of the original app:

- Found and fixed broken access control: most write endpoints (`POST`/`PUT`/`DELETE`) accepted requests with no authentication at all.
- Found and fixed a JWT signing secret and admin credentials hardcoded in the source, recoverable with a small dictionary attack.
- Found and fixed a NoSQL injection in the query filters (unsanitized operator injection via query string, e.g. `?field[$ne]=...`).
- Centralized authentication into a single middleware, moved secrets to environment variables, and sanitized filter input — applied consistently across the whole API (v1 and v2), not just the one endpoint that originally had (weak) auth.

The pentest only ever targeted a local instance, never the live deployment at sos2526-11.onrender.com, which is shared infrastructure Tomás and José still use.