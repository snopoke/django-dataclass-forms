from invoke import Context, task


@task
def test(c: Context):
    c.run("pytest")


@task
def test_all(c: Context):
    c.run("tox -p")


@task
def tag_release(c: Context):
    c.run("poetry check --no-interaction")

    version = _get_version(c)
    bump_key = input("Current version: {version}. Bump? [1: major, 2: minor, 3: patch / n]")
    if bump_key in ("1", "2", "3"):
        bump = {"1": "major", "2": "minor", "3": "patch"}.get(bump_key)

        c.run(f"poetry version {bump}")
        version = _get_version(c)
        c.run("git add pyproject.toml")
        c.run(f"git commit -m 'Bump version to {version}'")

    if input(f"\nReady to release version {version}? [y/n]") == "y":
        c.run(f"git tag v{version}")
        c.run("git push origin main --tags")

        print(
            "Check https://github.com/snopoke/django-dataclass-forms/actions/workflows/release.yml for release build."
        )
        print("Check https://github.com/snopoke/django-dataclass-forms/releases and publish the release.")


def _get_version(c):
    version = c.run("poetry version -s", hide="out").stdout.strip()
    return version
