import {routingKind} from './model.js';
const stages=['sessionPick','newLogin','changeTenancy','tenancy','domainOpen','domainPick','domain','credentials','username','alternative','bypassChoice','bypass'];
const kinds=['start','navigate','identity-ready','claim','applied','injected','injection-stale','injection-retry','error','stopped','complete'];
const hosts=['console','account-entry','broker','regional-broker','identity','other'];
const transitions=['link','typed','auto_bookmark','auto_subframe','manual_subframe','generated','start_page','form_submit','reload','keyword','keyword_generated'];
const qualifiers=['client_redirect','server_redirect','forward_back','from_address_bar'];
const reasons=['none','no-login-job','unsupported-origin','unverified-tenancy','navigation-rejected','page-error','access-denied','injection-failed','cancelled','expired','complete','existing'];
function event(e){return {kind:kinds.includes(e?.kind)?e.kind:'error',host:hosts.includes(e?.host)?e.host:'other',stage:stages.includes(e?.stage)?e.stage:undefined,transition:transitions.includes(e?.transition)?e.transition:undefined,qualifiers:(Array.isArray(e?.qualifiers)?e.qualifiers:[]).filter(q=>qualifiers.includes(q)).slice(0,4)};}
export function trace(job,kind,details={}){
  const entry=event({kind,host:routingKind(job.activeOrigin),...details});
  job.trace=[...(job.trace||[]),entry].slice(-24);
  if(entry.kind==='navigate'&&job.route?.at(-1)!==entry.host)job.route=[...(job.route||[]),entry.host].slice(-12);
}
export function snapshot(job){return {host:routingKind(job?.activeOrigin),tenancyVerified:job?.tenancyVerified===true,identityReady:!!job?.activeIdentity,applied:stages.filter(s=>job?.applied?.[s]===true),route:(job?.route||[]).filter(h=>hosts.includes(h)).slice(-12),events:(job?.trace||[]).slice(-24).map(event)};}
export function diagnosticReport(state,version,incognito){
  const s=state?.debug||{};
  return {version:/^\d+\.\d+\.\d+$/.test(version)?version:'unknown',incognito:incognito===true,status:[...stages,'waiting','broker','identity','stopped','complete','existing'].includes(state?.step)?state.step:'none',reason:reasons.includes(state?.reason)?state.reason:'no-login-job',host:hosts.includes(s.host)?s.host:'other',tenancyVerified:s.tenancyVerified===true,identityReady:s.identityReady===true,applied:stages.filter(k=>s.applied?.includes(k)),route:(Array.isArray(s.route)?s.route:[]).filter(h=>hosts.includes(h)).slice(-12),events:(Array.isArray(s.events)?s.events:[]).slice(-24).map(event)};
}
