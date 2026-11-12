/*
 * Geo-Portal markup. Rendered once; the engine (engine/geoportal.js)
 * then drives it through the data-* hooks, so this component must not re-render
 * with different props after the engine starts (see GeoPortalPage).
 */
import {
  ChevronDown, EllipsisVertical, Grid3x3, GripVertical, House, Info, Layers, Library, LocateFixed,
  Maximize, Minimize, Minus, PanelLeftClose, PanelLeftOpen, Pencil, Pentagon, Plus, Save, Scan,
  ScanSearch, Search, Spline, SquareDashed, Trash2, Upload, Download, X,
} from "lucide-react";
import { memo } from "react";
import { Link } from "react-router-dom";

import type { GeoportalConfig } from "@/features/geoportal/types";

type Props = { cfg: GeoportalConfig; signedIn: boolean; signInHref: string };

function MarkupImpl({ cfg, signedIn, signInHref }: Props) {
  const bm0 = cfg.basemaps[0];
  return (
    <>
      <div className="gp" data-gp="">
        <aside className="gp-side" id="gp-side" aria-label="Layers and tools">
          <div className="gp-side-head">
            <div><h1>Data Catalog</h1></div>
            <button type="button" className="gp-icon-btn" data-gp-collapse="" aria-controls="gp-side" aria-expanded="true" aria-label="Collapse panel" title="Collapse panel">
              <PanelLeftClose aria-hidden="true" />
            </button>
          </div>

          <div className="gp-tabs gp-tabs-2" role="tablist" aria-label="Panels" data-gp-tabs="">
            <button type="button" role="tab" id="gpt-active" aria-controls="gpp-active" aria-selected="true">
              <Layers aria-hidden="true" />Layers<span className="gp-count" data-gp-count="">0</span>
            </button>
            <button type="button" role="tab" id="gpt-area" aria-controls="gpp-area" aria-selected="false" tabIndex={-1}>
              <Pentagon aria-hidden="true" />Area
            </button>
          </div>

          {/* Layers on the map */}
          <div className="gp-panel" role="tabpanel" id="gpp-active" aria-labelledby="gpt-active">
            <div className="gp-layers-bar">
              <button type="button" className="gp-btn gp-btn-dark gp-btn-sm gp-catbtn" data-gp-open-catalog="" data-gp-catalog-toggle="" aria-controls="gp-catalog-win" aria-expanded="false" title="Open or close the data catalog">
                <Library aria-hidden="true" />Catalog
              </button>
            </div>
            <div className="gp-layers-bar"><span>On the map</span></div>
            <div className="gp-scroll">
              <ul className="gp-active" data-gp-active=""></ul>
              <div className="gp-empty-state" data-gp-active-empty="">
                <Layers aria-hidden="true" />
                <p><strong>No layers on the map</strong></p>
                <p>Open the data catalog to add rainfall, land cover, terrain and more.</p>
                <button type="button" className="gp-btn gp-btn-outline" data-gp-open-catalog="" aria-controls="gp-catalog-win">Browse catalog</button>
              </div>
            </div>
          </div>

          {/* Area of interest */}
          <div className="gp-panel" role="tabpanel" id="gpp-area" aria-labelledby="gpt-area" hidden>
            <div className="gp-scroll gp-pad">
              <div className="field gp-country">
                <label htmlFor="gp-country">Country</label>
                <select className="input" id="gp-country" data-gp-country="" defaultValue="">
                  <option value="">All member countries ({cfg.countries.length})</option>
                  {cfg.countries.map((c) => <option key={c.iso} value={c.iso}>{c.name}</option>)}
                </select>
              </div>
              {signedIn && (
                <div className="field gp-country">
                  <label htmlFor="gp-saved">Saved area</label>
                  <div className="gp-saved-row">
                    <select className="input" id="gp-saved" data-gp-saved="" disabled defaultValue="">
                      <option value="">Loading your areas…</option>
                    </select>
                    <div className="gp-more" data-menu="" data-gp-more="" hidden>
                      <button type="button" className="gp-btn gp-btn-outline gp-more-btn" data-menu-toggle="" aria-haspopup="menu" aria-expanded="false" aria-controls="gp-area-menu" aria-label="Actions for the selected area" title="More actions">
                        <EllipsisVertical aria-hidden="true" />
                      </button>
                      <div className="gp-more-menu" id="gp-area-menu" role="menu" data-menu-panel="">
                        <button type="button" role="menuitem" data-area-act="zoom"><Scan aria-hidden="true" />Zoom to area</button>
                        <button type="button" role="menuitem" data-area-act="rename"><Pencil aria-hidden="true" />Rename</button>
                        <button type="button" role="menuitem" data-area-act="download"><Download aria-hidden="true" />Download GeoJSON</button>
                        <span className="gp-more-sep" role="separator"></span>
                        <button type="button" role="menuitem" className="is-danger" data-area-act="delete"><Trash2 aria-hidden="true" />Delete</button>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              <p className="gp-lead">Define a project area to analyse. Draw it on the map or upload a GeoJSON file.</p>
              <div className="gp-draw" role="group" aria-label="Draw tools">
                <button type="button" className="gp-tool" data-gp-draw="Polygon"><Pentagon aria-hidden="true" />Polygon</button>
                <button type="button" className="gp-tool" data-gp-draw="Box"><SquareDashed aria-hidden="true" />Rectangle</button>
                <label className="gp-tool">
                  <Upload aria-hidden="true" />Upload
                  <input type="file" accept=".geojson,.json,application/geo+json" data-gp-upload="" hidden />
                </label>
              </div>
              <p className="gp-hint" data-gp-draw-hint="" hidden>Click on the map to add points. Double-click to finish. Press Esc to cancel.</p>
              <div className="gp-aoi" data-gp-aoi="" hidden>
                <div className="gp-aoi-head">
                  <strong data-gp-aoi-title="">Project area</strong>
                  <button type="button" className="gp-link" data-gp-clear="">Clear</button>
                </div>
                <dl className="gp-stats">
                  <div><dt>Area</dt><dd data-gp-area="">-</dd></div>
                  <div><dt>Perimeter</dt><dd data-gp-perim="">-</dd></div>
                </dl>
                <Link className="gp-btn gp-btn-dark" to="/analytics"><ScanSearch aria-hidden="true" />Analyse this area</Link>
                {signedIn && (
                  <button type="button" className="gp-btn gp-btn-outline" data-gp-save-open="" disabled hidden><Save aria-hidden="true" />Save area</button>
                )}
                <button type="button" className="gp-btn gp-btn-outline" data-gp-download="" disabled hidden><Download aria-hidden="true" />Download GeoJSON</button>
                {!signedIn && (
                  <p className="gp-save-signin"><Link to={signInHref}>Sign in</Link> to save this area to your projects.</p>
                )}
                <p className="gp-save-msg" data-gp-save-msg="" role="status" hidden></p>
              </div>
            </div>
          </div>
        </aside>

        <div className="gp-map-wrap" data-gp-mapwrap="">
          <div id="gp-map" className="gp-map" tabIndex={0} aria-label="Map"></div>

          <div className="gp-topleft">
            <button type="button" className="gp-expand" data-gp-expand="" aria-controls="gp-side" aria-label="Show panel" hidden>
              <PanelLeftOpen aria-hidden="true" /><span>Layers</span>
            </button>
            <div className="bmp" data-menu="">
              <button type="button" className="bmp-btn" aria-expanded="false" aria-controls="gp-basemaps" data-menu-toggle="">
                <img src={bm0.thumb} alt="" data-gp-bm-thumb="" />
                <span><small>Basemap</small><strong data-gp-bm-name="">{bm0.name}</strong></span>
              </button>
              <div className="bmp-menu" id="gp-basemaps" data-menu-panel="" role="radiogroup" aria-label="Basemap">
                {cfg.basemaps.map((b, i) => (
                  <button key={b.id} type="button" role="radio" className={`bmp-opt${i === 0 ? " is-on" : ""}`} aria-checked={i === 0} data-gp-basemap={b.id}>
                    <img src={b.thumb} alt="" loading="lazy" />
                    <span>{b.name}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <section className="gp-catwin" id="gp-catalog-win" role="dialog" aria-labelledby="gp-catalog-title" aria-modal="false" hidden data-gp-catwin="">
            <header className="gp-catwin-head" data-gp-drag="" title="Drag to move">
              <GripVertical className="gp-grip" aria-hidden="true" />
              <div className="gp-catwin-title">
                <h2 id="gp-catalog-title">Data catalog</h2>
                <p>{cfg.live_count} live layers · {cfg.total_count} in total</p>
              </div>
              <button type="button" className="gp-icon-btn" data-gp-close-catalog="" aria-label="Close catalog" title="Close"><X aria-hidden="true" /></button>
            </header>
            <div className="gp-catwin-body">
              <div className="gp-tools">
                <label className="gp-search">
                  <Search aria-hidden="true" />
                  <span className="visually-hidden">Search layers</span>
                  <input type="search" placeholder="Search layers or sources" data-gp-search="" autoComplete="off" />
                </label>
                <div className="gp-filter" role="group" aria-label="Layer type" data-gp-filter="">
                  <button type="button" className="is-on" data-type="all" aria-pressed="true">All</button>
                  <button type="button" data-type="raster" aria-pressed="false">Raster</button>
                  <button type="button" data-type="vector" aria-pressed="false">Vector</button>
                </div>
              </div>
              <div className="gp-scroll">
                {cfg.catalog.map((g) => (
                  <details key={g.group} className="gp-group" data-type={g.type} open>
                    <summary>
                      <span className="gp-group-type">{g.type === "raster" ? <Grid3x3 aria-hidden="true" /> : <Spline aria-hidden="true" />}</span>
                      <span className="gp-group-name">{g.group}</span>
                      <span className="gp-group-n">{g.layers.length}</span>
                      <ChevronDown className="gp-chev" aria-hidden="true" />
                    </summary>
                    <ul>
                      {g.layers.map((l) => (
                        <li key={l.id} className={`gp-item${l.kind === "planned" ? " is-planned" : ""}`} data-layer={l.id} data-search={`${l.name.toLowerCase()} ${l.source.toLowerCase()}`}>
                          <label className="gp-switch">
                            <input type="checkbox" data-gp-toggle={l.id} disabled={l.kind === "planned"} />
                            <span className="gp-switch-ui" aria-hidden="true"></span>
                            <span className="visually-hidden">Show {l.name}</span>
                          </label>
                          <div className="gp-item-body">
                            <span className="gp-item-name">{l.name}</span>
                            <span className="gp-item-meta">{l.source} · {l.res}</span>
                          </div>
                          {l.kind === "planned" && <span className="gp-badge">Planned</span>}
                          {l.view_only === true && <span className="gp-badge" title="A picture from an outside service: no values, no download">View only</span>}
                          <button type="button" className="gp-icon-btn gp-info-btn" aria-expanded="false" aria-controls={`info-${l.id}`} aria-label={`About ${l.name}`} data-gp-info="">
                            <Info aria-hidden="true" />
                          </button>
                          <div className="gp-info" id={`info-${l.id}`} hidden>
                            <p>{l.desc}</p>
                            <dl>
                              <div><dt>Source</dt><dd>{l.source}</dd></div>
                              <div><dt>Resolution</dt><dd>{l.res}</dd></div>
                              <div><dt>Period</dt><dd>{l.period}</dd></div>
                              <div><dt>Status</dt><dd>{l.kind === "planned" ? "Planned for the GEIDA data lake" : l.view_only === true ? "View only (picture from an outside service)" : "Live"}</dd></div>
                            </dl>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </details>
                ))}
                <p className="gp-empty" data-gp-noresults="" hidden>No layers match your search.</p>
              </div>
            </div>
          </section>


          <div className="gp-ctrl" role="toolbar" aria-label="Map controls">
            <div className="gp-ctrl-group">
              <button type="button" data-gp-zoom="1" aria-label="Zoom in" title="Zoom in"><Plus aria-hidden="true" /></button>
              <button type="button" data-gp-zoom="-1" aria-label="Zoom out" title="Zoom out"><Minus aria-hidden="true" /></button>
            </div>
            <div className="gp-ctrl-group">
              <button type="button" data-gp-home="" aria-label="Home extent: all member countries" title="Home extent"><House aria-hidden="true" /></button>
              <button type="button" data-gp-locate="" aria-label="Go to my location" title="My location"><LocateFixed aria-hidden="true" /></button>
              <button type="button" data-gp-fullscreen="" aria-label="Full screen" title="Full screen">
                <Maximize className="when-off" aria-hidden="true" /><Minimize className="when-on" aria-hidden="true" />
              </button>
            </div>
          </div>

          <div className="gp-status">
            <span className="gp-coords" data-gp-coords="">Move over the map</span>
            <span className="gp-sep" aria-hidden="true"></span>
            <span>Zoom <b data-gp-zoomlevel="">3</b></span>
            <div className="gp-scale" data-gp-scale=""></div>
          </div>

          <div className="gp-popup" data-gp-popup="" hidden>
            <button type="button" className="gp-popup-close" aria-label="Close" data-gp-popup-close=""><X aria-hidden="true" /></button>
            <div data-gp-popup-body=""></div>
          </div>
        </div>
      </div>

      {signedIn && (
        <>
          <dialog className="gp-dialog" data-gp-save-dialog="" aria-labelledby="gp-save-title">
            <form method="dialog" data-gp-save="" noValidate>
              <h2 id="gp-save-title">Save area</h2>
              <p className="gp-dialog-sub" data-gp-save-sub=""></p>
              <label htmlFor="gp-area-name">Name</label>
              <input className="input" id="gp-area-name" type="text" maxLength={120} placeholder="e.g. Kano irrigation scheme" autoComplete="off" data-gp-area-name="" />
              <p className="gp-dialog-err" data-gp-save-err="" role="alert" hidden></p>
              <div className="gp-dialog-actions">
                <button type="button" className="gp-btn gp-btn-outline" data-gp-dialog-cancel="">Cancel</button>
                <button type="submit" className="gp-btn gp-btn-dark"><Save aria-hidden="true" />Save</button>
              </div>
            </form>
          </dialog>
          <dialog className="gp-dialog" data-gp-delete-dialog="" aria-labelledby="gp-del-title">
            <form method="dialog" data-gp-delete-form="">
              <h2 id="gp-del-title">Delete area?</h2>
              <p className="gp-dialog-sub" data-gp-delete-sub=""></p>
              <p className="gp-dialog-err" data-gp-delete-err="" role="alert" hidden></p>
              <div className="gp-dialog-actions">
                <button type="button" className="gp-btn gp-btn-outline" data-gp-dialog-cancel="">Cancel</button>
                <button type="submit" className="gp-btn gp-btn-danger"><Trash2 aria-hidden="true" />Delete</button>
              </div>
            </form>
          </dialog>
        </>
      )}
    </>
  );
}

export const Markup = memo(MarkupImpl);
