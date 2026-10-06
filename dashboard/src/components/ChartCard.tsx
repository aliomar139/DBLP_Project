import type { ReactNode } from 'react'

export function ChartCard({title,description,action,children,id}:{title:string;description?:string;action?:ReactNode;children:ReactNode;id?:string}) {
 return <section id={id} className="chart-card"><header className="section-heading"><div><h2>{title}</h2>{description&&<p>{description}</p>}</div>{action}</header>{children}</section>
}

export function ResourceState({error,retry}:{error?:string;retry:()=>void}) {
 return error?<div className="resource-state error" role="alert"><p>{error}</p><button onClick={retry}>Try again</button></div>:<div className="resource-state" role="status"><span className="loading-line"/>Loading research data...</div>
}

export function PageHeader({title,description,children}:{title:string;description:ReactNode;children?:ReactNode}) {
 return <header className="page-heading"><h1>{title}</h1>{typeof description === 'string' ? <p>{description}</p> : <div>{description}</div>}{children}</header>
}
