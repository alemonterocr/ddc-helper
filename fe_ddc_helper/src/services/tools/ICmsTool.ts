/**
 * Contract for every CMS tool that can be dispatched by the WSClientAdapter.
 *
 * TArgs  – the shape of the args object the backend sends in the tool_call message
 * TResult – the result shape returned to the backend via tool_result
 */
export interface ICmsTool<TArgs = Record<string, unknown>, TResult = unknown> {
  /** Must match the tool name string used in ToolCallMessage.tool */
  readonly name: string

  /**
   * Which browser tab this tool injects into.
   * - 'cms'        → *.website.dealercenter.coxautoinc.com  (ISOLATED world, JSESSIONID auth)
   * - 'media_lib'  → apps.dealercenter.coxautoinc.com       (MAIN world, JWTAuth cookie)
   * - 'salesforce' → casfx.lightning.force.com              (MAIN world, sid cookie)
   */
  readonly domain: 'cms' | 'media_lib' | 'salesforce'

  execute(args: TArgs, tabId: number, token: string): Promise<TResult>
}
