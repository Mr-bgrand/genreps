# GenREPS

Searchable watch gallery built from public Dropbox folders, with In Stock and Inbound filters and a selected cover per watch.

## Vercel deployment

Existing project: `watch-collection` in `mrbgrands-projects`.
Production URL: https://watch-collection-mrbgrands-projects.vercel.app/
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

The build publishes only `public/index.html` and `public/refresh.html`. Photos are embedded in the gallery, avoiding expiring thumbnail URLs. Generated data, caches, credentials, and virtual environments are excluded from Git.

## Cover selection

135 reviewed choices are pinned in `covers.json`. New watches use a filename hint or a suggested third photo; this is not visual recognition. Use the original cover-review updater to review additions, copy the updated covers.json here, and push. The hosted build does not use the optional paid AI selector.

## Maintenance

Public Dropbox page parsing is unofficial and may need updating if Dropbox changes its website. Failed or incomplete imports stop the build. Prices and authenticity are not inferred.

Run importer tests with `python3 -m unittest discover -s tests -v`.
