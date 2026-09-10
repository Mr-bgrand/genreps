# GenREPS

Searchable watch gallery built from public Dropbox folders, with In Stock and Inbound filters and a selected cover per watch.

## Vercel deployment

Git-linked project: `genreps` in `mrbgrands-projects`.
Original gallery / migration source: https://watch-collection-mrbgrands-projects.vercel.app/
GitHub repository: https://github.com/Mr-bgrand/genreps

Connect this repository in the existing Vercel project under **Settings → Git**. Use `main` as the production branch, the repository root as the root directory, and Other as the framework. `vercel.json` supplies the install command, build command, and public output directory. Pushes to main will trigger builds once the Git integration is connected.

## Refresh inventory

Every build fetches both Dropbox sources again. To refresh without code changes, use **Deployments → Redeploy** on the latest successful production deployment. The gallery has an owner refresh link with instructions. Only signed-in Vercel project members can publish. No automatic schedule is configured.

The current gallery remains live if a build fails. Updates can take several minutes. No Dropbox login, runtime database, or paid AI service is required.

## Local use

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 build_site.py
python3 -m http.server 8000 --directory public
```

The build publishes a photo viewer, `catalog.json`, and active-watch image files. Only still photos are imported; videos are excluded. Active watches show all available photos. Archived watches retain a single JPEG cover, stored once in catalog.json, with no extra photo files.

## Sold archive

A successful refresh compares both Dropbox sources with the previous production catalog. A missing stock number, or folder ID when there is no stock number, moves the watch into Sold Archive. Moving a stock number between folders or between Inbound and In Stock does not mark it sold. Reappearing stock numbers become active again. Folders still present without supported photos retain their last cover and remain active.

Archive entries are grouped by brand and model inferred from folder titles; unrecognized names go under Other brands / Other models. The archive date is the detection time, not an asserted sale date.

**Archive persistence:** Each build reads the last successful production deployment at its own production domain, using Vercel’s `VERCEL_PROJECT_PRODUCTION_URL` before importing Dropbox. The first update migrates the old embedded gallery automatically. If the prior catalog is inaccessible, invalid, or missing photos, the build fails rather than resetting history. Keep this production URL public and stable. Outside Vercel, the original watch-collection URL is used as the default migration source. The current deployment is the archive store; rolling back to an older deployment also restores its older archive. Download catalog.json as a backup before rollbacks. Serialize production refreshes so concurrent builds cannot replace newer history.

Missing photos from sold watches are removed from the new deployment output. Historical Vercel deployments are retained according to Vercel's own retention settings; this code does not delete previous deployments.

Generated data, caches, credentials, and virtual environments are excluded from Git.

## Cover selection

135 original reviewed choices are pinned in `covers.json`. New watches use a filename hint or a suggested third photo; this is not visual recognition. Use the original cover-review updater to review additions, copy the updated covers.json here, and push. The hosted build does not use the optional paid AI selector.

## Maintenance

Public Dropbox page parsing is unofficial and may need updating if Dropbox changes its website. Failed or incomplete imports stop the build. Prices and authenticity are not inferred.

Run importer tests with `python3 -m unittest discover -s tests -v`.
