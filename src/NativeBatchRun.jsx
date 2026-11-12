import React, { useEffect,useState } from 'react';
import { Alert,Button,Chip,LinearProgress,Stack,Typography } from '@mui/material';
import { loadNativeRun } from './nativeCatalog';

export default function NativeBatchRun({onCatalogRefresh}) {
  const [run,setRun]=useState(null),[error,setError]=useState('');
  useEffect(()=>{
    const ctrl=new AbortController();let timer;
    async function read(){
      try {
        const data=await loadNativeRun(ctrl.signal); if(ctrl.signal.aborted)return;
        setRun(data);setError('');
        if(data && ['running','waiting_for_gpu','prepared'].includes(data.state))timer=setTimeout(read,30000);
      } catch(e){if(e.name!=='AbortError')setError(e.message);}
    }
    read();return()=>{ctrl.abort();clearTimeout(timer);};
  },[]);
  if(error)return <Alert severity="warning" sx={{mb:2}}>{error}</Alert>;
  if(!run)return null;
  return <section className="native-run-card">
    <Stack direction="row" sx={{justifyContent:'space-between',gap:2,flexWrap:'wrap'}}><Typography component="h2" variant="h6">Native pixel overlay expansion</Typography><Chip label={run.state.replaceAll('_',' ')} /></Stack>
    <Typography sx={{my:1}}>{run.processed.toLocaleString()} of {run.candidates.toLocaleString()} candidates checked · {(run.outcomes.ready||0).toLocaleString()} ready · {(run.outcomes.excluded||0).toLocaleString()} excluded · {(run.outcomes.deferred||0).toLocaleString()} deferred</Typography>
    <LinearProgress variant="determinate" value={100*run.processed/run.candidates} />
    <Typography variant="body2" sx={{mt:1}}>Frozen model · one worker · no Supabase requests during generation. Updated {new Date(run.updated_at).toLocaleString()}.</Typography>
    <Typography variant="body2" color="text.secondary" sx={{mt:1}}>Every cached candidate is recorded in the manifest. Outcomes are saved as processing completes, including quality exclusions. The expanded collection includes multiple evaluation splits; fine-scale accuracy and hardware screening remain unverified.</Typography>
    <Button sx={{mt:1}} onClick={()=>onCatalogRefresh().catch(e=>setError(e.message))}>Load completed overlays into cohort</Button>
    <details><summary>Run provenance and exclusions</summary><p>Run: {run.run_id}</p><p className="hash">Checkpoint: {run.checkpoint_sha256}</p><p>{Object.entries(run.split_counts).map(([k,v])=>`${v.toLocaleString()} ${k}`).join(' · ')}</p>{Object.entries(run.exclusion_reasons).map(([k,v])=><p key={k}>{k.replaceAll('_',' ')}: {v.toLocaleString()}</p>)}</details>
  </section>;
}
