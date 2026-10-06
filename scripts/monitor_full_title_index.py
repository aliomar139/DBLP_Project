"""Record local build-process and sidecar disk measurements until it exits."""
import argparse,json,os,sys,time
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.work/rag-benchmark/packages'))
import psutil

def tree_bytes(path):
    total=0
    for root,dirs,files in os.walk(path):
        for name in files:
            try:total+=(Path(root)/name).stat().st_size
            except OSError:pass
    return total

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pid',type=int,required=True);ap.add_argument('--sidecar',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--interval',type=int,default=30);a=ap.parse_args()
    p=psutil.Process(a.pid);started=datetime.now(timezone.utc);peak_rss=0;peak_sidecar=0;free_start=psutil.disk_usage(str(a.sidecar.resolve().anchor)).free;free_min=free_start;sample_count=0;exit_code=None
    while True:
        try:rss=p.memory_info().rss
        except psutil.Error:break
        peak_rss=max(peak_rss,rss);size=tree_bytes(a.sidecar);peak_sidecar=max(peak_sidecar,size);free=psutil.disk_usage(str(a.sidecar.resolve().anchor)).free;free_min=min(free_min,free);sample_count+=1
        try:
            status=json.loads(a.manifest.read_text(encoding='utf-8')).get('status')
        except (OSError,ValueError):status=None
        if status in ('ready','interrupted'):break
        time.sleep(a.interval)
    try:exit_code=p.wait(timeout=0)
    except psutil.Error:exit_code=None
    final_size=tree_bytes(a.sidecar)
    result={'started_at_utc':started.isoformat(),'ended_at_utc':datetime.now(timezone.utc).isoformat(),'target_pid':a.pid,'target_exit_code':exit_code,'samples':sample_count,'sample_interval_seconds':a.interval,'builder_peak_working_set_bytes':peak_rss,'sidecar_peak_bytes_sampled':peak_sidecar,'sidecar_final_bytes':final_size,'drive_free_bytes_at_monitor_start':free_start,'drive_free_bytes_min_sampled':free_min,'drive_free_change_bytes_sampled':free_start-free_min,'final_manifest_status':status,'qualification':'Disk free-space change is system-wide; sampled sidecar bytes include artifacts in its directory but exclude temporary files outside it.'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
