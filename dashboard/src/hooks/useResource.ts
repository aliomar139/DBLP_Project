import { useEffect, useState } from 'react'

// Keyed state prevents the previous researcher's data flashing after navigation.
export function useResource<T>(key:string, fetcher:(signal:AbortSignal)=>Promise<T>) {
 const [attempt,setAttempt]=useState(0)
 const [state,setState]=useState<{key:string;data?:T;error?:string}>({key:''})
 useEffect(()=>{
  const controller=new AbortController()
  setState({key})
  fetcher(controller.signal).then(data=>{if(!controller.signal.aborted)setState({key,data})})
   .catch((error:Error)=>{if(!controller.signal.aborted)setState({key,error:error.message})})
  return ()=>controller.abort()
  // Fetcher is deliberately represented by the explicit resource key.
  // eslint-disable-next-line react-hooks/exhaustive-deps
 },[key,attempt])
 return {data:state.key===key?state.data:undefined,error:state.key===key?state.error:undefined,retry:()=>setAttempt(n=>n+1)}
}
