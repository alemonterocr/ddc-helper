export interface SectionInjectionResult {
  success: boolean
  error?: string
}

export interface CMSPort {
  injectSection(
    dealerId: string,
    token: string,
    pageAlias: string,
    sectionType: string,
  ): Promise<SectionInjectionResult>
}
