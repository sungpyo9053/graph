let discoveryPollTimer=null;
async function startDiscovery(){
  const button=document.querySelector('#discoverButton');
  if(button)button.disabled=true;
  showDiscoveryJob({status:'QUEUED',job_id:'요청 중',llm_provider:''});
  try{
    const response=await fetch('/api/v1/discovery-jobs',{method:'POST'});
    if(!response.ok){const body=await response.json();throw new Error(body.detail||'실행을 시작하지 못했습니다.');}
    const job=await response.json();
    localStorage.setItem('discoveryJobId',job.job_id);
    showDiscoveryJob(job);
    pollDiscoveryJob(job.job_id);
  }catch(error){
    showDiscoveryJob({status:'FAILED',job_id:'',error:String(error.message||error)});
    if(button)button.disabled=false;
  }
}
async function pollDiscoveryJob(jobId){
  if(discoveryPollTimer)clearTimeout(discoveryPollTimer);
  try{
    const response=await fetch(`/api/v1/discovery-jobs/${jobId}`);
    if(!response.ok)throw new Error('실행 상태를 불러오지 못했습니다.');
    const job=await response.json();
    showDiscoveryJob(job);
    if(job.status==='COMPLETED'||job.status==='FAILED'){
      localStorage.removeItem('discoveryJobId');
      const button=document.querySelector('#discoverButton');
      if(button)button.disabled=false;
      return;
    }
    discoveryPollTimer=setTimeout(()=>pollDiscoveryJob(jobId),2000);
  }catch(error){
    showDiscoveryJob({status:'FAILED',job_id:jobId,error:String(error.message||error)});
    localStorage.removeItem('discoveryJobId');
    const button=document.querySelector('#discoverButton');
    if(button)button.disabled=false;
  }
}
function showDiscoveryJob(job){
  const panel=document.querySelector('#discoveryJob');
  if(!panel)return;
  panel.hidden=false;
  const labels={QUEUED:'실행 대기',RUNNING:'그래프 실행 중',COMPLETED:'아이디어 탐색 완료',FAILED:'실행 실패'};
  document.querySelector('#jobLabel').textContent=labels[job.status]||job.status;
  document.querySelector('#jobMeta').textContent=job.error||[job.job_id&&`job ${job.job_id.slice(0,8)}`,job.llm_provider&&`LLM ${job.llm_provider}`].filter(Boolean).join(' · ');
  const result=document.querySelector('#jobResult');
  if(job.status==='COMPLETED'&&job.result_url){result.href=job.result_url;result.hidden=false;}else{result.hidden=true;}
}
document.addEventListener('DOMContentLoaded',()=>{
  const jobId=localStorage.getItem('discoveryJobId');
  if(jobId){const button=document.querySelector('#discoverButton');if(button)button.disabled=true;pollDiscoveryJob(jobId);}
});
async function approve(id,decision){const reason=document.querySelector('#approvalReason')?.value||'';const revise_node=decision==='REVISE'?document.querySelector('#reviseNode').value:null;const response=await fetch(`/api/v1/approvals/${id}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision,revise_node,reason})});if(!response.ok)alert(await response.text());else location.reload()}
function filterRows(){const status=document.querySelector('#statusFilter')?.value||'';const risk=document.querySelector('#riskFilter')?.value||'';const confidence=Number(document.querySelector('#confidenceFilter')?.value||0);document.querySelectorAll('tbody tr[data-status]').forEach(row=>row.hidden=!!((status&&row.dataset.status!==status)||(risk&&row.dataset.risk!==risk)||Number(row.dataset.confidence)<confidence))}
document.querySelectorAll('.filters input,.filters select').forEach(x=>x.addEventListener('input',filterRows));
