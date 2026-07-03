import type { ICmsTool } from './ICmsTool'
import { CheckPageExistsTool } from './CheckPageExistsTool'
import { CreatePageTool } from './CreatePageTool'
import { CreateMediaFolderTool } from './CreateMediaFolderTool'
import { GetMediaFoldersTool } from './GetMediaFoldersTool'
import { GetPageAliasByPathTool } from './GetPageAliasByPathTool'
import { GetPageLayoutTool } from './GetPageLayoutTool'
import { InjectItemListTool } from './InjectItemListTool'
import { InjectSectionTool } from './InjectSectionTool'
import { InjectStaffListingTool } from './InjectStaffListingTool'
import { SaveContentTool } from './SaveContentTool'
import { SavePageLayoutTool } from './SavePageLayoutTool'
import { SetWindowPreferencesTool } from './SetWindowPreferencesTool'
import { SfUiApiGetTool } from './SfUiApiGetTool'
import { UploadMediaImageTool } from './UploadMediaImageTool'
import { UpdateSiteLabelsTool } from './UpdateSiteLabelsTool'

export type { ICmsTool }
export {
  CheckPageExistsTool,
  CreateMediaFolderTool,
  CreatePageTool,
  GetMediaFoldersTool,
  GetPageAliasByPathTool,
  GetPageLayoutTool,
  InjectItemListTool,
  InjectSectionTool,
  InjectStaffListingTool,
  SaveContentTool,
  SavePageLayoutTool,
  SetWindowPreferencesTool,
  SfUiApiGetTool,
  UpdateSiteLabelsTool,
  UploadMediaImageTool,
}

/**
 * Central tool registry.
 * Add a new tool class here — the dispatcher picks it up automatically.
 *
 * ICmsTool<any> is intentional: the registry is a heterogeneous lookup table.
 * Type safety is enforced by each concrete tool class; the dispatcher erases
 * args types at the call site with `as never`.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _tools: Array<ICmsTool<any>> = [
  new CheckPageExistsTool(),
  new CreateMediaFolderTool(),
  new CreatePageTool(),
  new GetMediaFoldersTool(),
  new GetPageAliasByPathTool(),
  new GetPageLayoutTool(),
  new InjectItemListTool(),
  new InjectSectionTool(),
  new InjectStaffListingTool(),
  new SaveContentTool(),
  new SavePageLayoutTool(),
  new SetWindowPreferencesTool(),
  new SfUiApiGetTool(),
  new UpdateSiteLabelsTool(),
  new UploadMediaImageTool(),
]

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const toolRegistry: ReadonlyMap<string, ICmsTool<any>> = new Map(
  _tools.map(t => [t.name, t]),
)
