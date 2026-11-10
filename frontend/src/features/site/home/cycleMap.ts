// Illustrative project-area map for the project-cycle section (static SVG).
export const CYCLE_SVG = `<svg viewBox="0 0 520 380" role="img" aria-labelledby="map-cap">
          <defs>
            <clipPath id="aoi-clip"><path d="M150 70C210 48 300 52 350 80 400 105 432 150 428 205 424 262 392 305 335 325 280 345 210 338 168 310 120 280 96 230 104 175 110 125 118 92 150 70Z"/></clipPath>
            <pattern id="p-slope" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="8" fill="#EBC889"/><line x1="0" y1="0" x2="0" y2="8" stroke="#D49A45" stroke-width="3"/></pattern>
            <pattern id="p-protect" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)"><line x1="0" y1="0" x2="0" y2="7" stroke="#2F8F4E" stroke-width="2"/></pattern>
            <pattern id="p-landuse" width="66" height="44" patternUnits="userSpaceOnUse"><rect width="22" height="22" fill="#8CC07A"/><rect x="22" width="22" height="22" fill="#E3D58C"/><rect x="44" width="22" height="22" fill="#5EA25B"/><rect y="22" width="22" height="22" fill="#E3D58C"/><rect x="22" y="22" width="22" height="22" fill="#A8CF8E"/><rect x="44" y="22" width="22" height="22" fill="#B9A3D3"/><path d="M0 0H66M0 22H66M0 44H66M0 0V44M22 0V44M44 0V44" stroke="#fff" stroke-width="1.5"/></pattern>
            <pattern id="p-ndvi" width="66" height="44" patternUnits="userSpaceOnUse"><rect width="22" height="22" fill="#9ED07F"/><rect x="22" width="22" height="22" fill="#5FAE52"/><rect x="44" width="22" height="22" fill="#CFE6A6"/><rect y="22" width="22" height="22" fill="#5FAE52"/><rect x="22" y="22" width="22" height="22" fill="#E7EFC2"/><rect x="44" y="22" width="22" height="22" fill="#86C26B"/><path d="M0 0H66M0 22H66M0 44H66M0 0V44M22 0V44M44 0V44" stroke="#fff" stroke-width="1.5"/></pattern>
            <pattern id="p-end" width="66" height="44" patternUnits="userSpaceOnUse"><rect width="22" height="22" fill="#3E8E3E"/><rect x="22" width="22" height="22" fill="#2E7A34"/><rect x="44" width="22" height="22" fill="#5BA64F"/><rect y="22" width="22" height="22" fill="#5BA64F"/><rect x="22" y="22" width="22" height="22" fill="#3E8E3E"/><rect x="44" y="22" width="22" height="22" fill="#77B95F"/><path d="M0 0H66M0 22H66M0 44H66M0 0V44M22 0V44M44 0V44" stroke="#fff" stroke-width="1.5"/></pattern>
            <pattern id="p-trend" width="66" height="44" patternUnits="userSpaceOnUse"><rect width="22" height="22" fill="#4E9E45"/><rect x="22" width="22" height="22" fill="#F0DE7A"/><rect x="44" width="22" height="22" fill="#8CC56B"/><rect y="22" width="22" height="22" fill="#8CC56B"/><rect x="22" y="22" width="22" height="22" fill="#4E9E45"/><rect x="44" y="22" width="22" height="22" fill="#EFA35B"/><path d="M0 0H66M0 22H66M0 44H66M0 0V44M22 0V44M44 0V44" stroke="#fff" stroke-width="1.5"/></pattern>
          </defs>

          <rect width="520" height="380" fill="#F1EADB"/>
          <g fill="none" stroke="#C9B48A" stroke-width="1" opacity=".55">
            <path d="M0 300C80 280 120 330 200 350S340 360 400 380"/>
            <path d="M0 330C70 315 110 355 170 380"/>
            <path d="M440 20C470 60 500 70 520 66"/>
            <path d="M400 0C430 50 480 90 520 96"/>
            <path d="M0 210C30 200 60 230 70 260S60 330 90 380"/>
          </g>
          <path d="M20 40C60 20 120 30 140 60 150 80 120 100 95 98 60 96 30 80 20 60Z" fill="#9CC3DE"/>
          <path d="M478 0C470 120 452 250 436 380" stroke="#9AA3AB" stroke-width="5" fill="none"/>

          <g class="layer" data-stage="pcn">
            <g clip-path="url(#aoi-clip)">
              <path d="M100 150C140 140 160 180 150 230 140 280 160 320 120 330L90 330 90 150Z" fill="url(#p-slope)"/>
              <path d="M330 90C380 110 420 140 430 180L430 90Z" fill="url(#p-slope)" opacity=".8"/>
              <path d="M128 78C170 120 230 150 250 200 268 250 255 300 262 334" stroke="#2B74B8" stroke-opacity=".18" stroke-width="34" fill="none"/>
            </g>
            <g class="pin"><circle cx="305" cy="160" r="11" fill="#fff" stroke="#0B2540" stroke-width="2"/><circle cx="305" cy="160" r="4" fill="#0B2540"/></g>
            <g class="pin"><circle cx="220" cy="240" r="11" fill="#fff" stroke="#0B2540" stroke-width="2"/><circle cx="220" cy="240" r="4" fill="#0B2540"/></g>
          </g>

          <g class="layer" data-stage="pprr">
            <rect width="520" height="380" fill="url(#p-landuse)" clip-path="url(#aoi-clip)" opacity=".92"/>
            <g fill="#7A5BC0" fill-opacity=".18" stroke="#7A5BC0" stroke-opacity=".5" stroke-dasharray="3 3">
              <circle cx="205" cy="112" r="42"/><circle cx="372" cy="178" r="42"/><circle cx="252" cy="292" r="42"/>
            </g>
          </g>

          <g class="layer" data-stage="pad">
            <rect width="520" height="380" fill="url(#p-landuse)" clip-path="url(#aoi-clip)" opacity=".55"/>
            <path d="M138 52C205 26 310 30 368 62 425 92 458 145 452 207 446 272 410 322 345 345 282 368 200 360 152 328 98 294 72 236 80 172 86 116 100 78 138 52Z" fill="none" stroke="#C07A22" stroke-width="2" stroke-dasharray="7 5"/>
            <path d="M40 262 102 248 116 330 52 350Z" fill="url(#p-protect)" stroke="#2F8F4E" stroke-width="1.5"/>
          </g>

          <g class="layer" data-stage="piasr">
            <rect width="520" height="380" fill="url(#p-ndvi)" clip-path="url(#aoi-clip)"/>
            <path d="M300 92C330 140 360 160 412 172" stroke="#D0368A" stroke-width="3" fill="none" stroke-dasharray="8 4"/>
            <path d="M160 260C190 250 210 270 240 268" stroke="#D0368A" stroke-width="3" fill="none"/>
            <g class="alert" fill="#C2412D" stroke="#fff" stroke-width="1.5">
              <path d="M232 138 244 158H220Z"/><path d="M384 228 396 248H372Z"/><path d="M152 218 164 238H140Z"/>
            </g>
          </g>

          <g class="layer" data-stage="pcr">
            <rect width="520" height="380" fill="url(#p-end)" clip-path="url(#aoi-clip)"/>
            <g stroke="#173F8A" stroke-width="3.5" fill="none">
              <path d="M250 200C300 196 340 214 390 222"/><path d="M190 160C170 190 150 220 140 250"/>
            </g>
          </g>

          <g class="layer" data-stage="pper">
            <rect width="520" height="380" fill="url(#p-trend)" clip-path="url(#aoi-clip)"/>
            <circle cx="470" cy="300" r="34" fill="#F0DE7A" fill-opacity=".45" stroke="#0B2540" stroke-width="1.5" stroke-dasharray="5 4"/>
          </g>

          <path d="M128 78C170 120 230 150 250 200 268 250 255 300 262 334" stroke="#2B74B8" stroke-width="3.5" fill="none"/>
          <g stroke="#5B9BD5" stroke-width="1.6" fill="none" clip-path="url(#aoi-clip)">
            <path d="M170 116C200 100 240 96 280 104"/><path d="M228 160C270 150 320 160 360 150"/><path d="M252 236C290 236 330 250 370 262"/><path d="M246 270C210 274 180 286 160 300"/>
          </g>
          <path d="M150 70C210 48 300 52 350 80 400 105 432 150 428 205 424 262 392 305 335 325 280 345 210 338 168 310 120 280 96 230 104 175 110 125 118 92 150 70Z" fill="none" stroke="#B42318" stroke-width="2.2"/>
          <g fill="#0B2540">
            <rect x="196" y="104" width="6" height="6"/><rect x="204" y="110" width="6" height="6"/><rect x="198" y="114" width="5" height="5"/>
            <rect x="364" y="170" width="6" height="6"/><rect x="372" y="176" width="6" height="6"/><rect x="366" y="181" width="5" height="5"/>
            <rect x="244" y="284" width="6" height="6"/><rect x="252" y="290" width="6" height="6"/><rect x="246" y="295" width="5" height="5"/>
          </g>
        </svg>`;
