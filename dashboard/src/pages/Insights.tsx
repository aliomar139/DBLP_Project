import { api } from '../api'
import { useResource } from '../hooks/useResource'
import { PageHeader, ResourceState } from '../components/ChartCard'
import { InsightExplorer } from '../components/InsightExplorer'
import { useInteraction } from '../components/InteractionContext'

export default function Insights() {
 const state = useResource('insights', api.insights)
 const { shareView } = useInteraction()
 return <>
  <PageHeader title="What the data tells us." description="Observations calculated from the indexed publication and collaboration records."/>
  {!state.data ? <ResourceState {...state}/> : <>
   <div className="insights-toolbar"><p className="coverage">Annual comparisons through {state.data.through_year} · Calculated on request; cached for up to ten minutes</p><button type="button" className="text-button" onClick={shareView}>Share this evidence view</button></div>
   <div className="insight-list">{state.data.items.length ? state.data.items.map((item, index) => <InsightExplorer item={item} index={index} key={item.title}/>) : <p className="empty-state">There are not enough indexed records to calculate insights.</p>}</div>
  </>}
 </>
}

