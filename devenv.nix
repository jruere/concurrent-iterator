{ pkgs, config, inputs, lib, ... }:

let
  pythonVersions = [ "3.9" "3.10" "3.11" "3.12" "3.13"];
  oldPythons = map
    (version: inputs.nixpkgs-python.packages.${pkgs.system}.${version})
    pythonVersions;

  envs = [
    { name = "py39"; bin = "python3.9"; }
    { name = "py310"; bin = "python3.10"; }
    { name = "py311"; bin = "python3.11"; }
    { name = "py312"; bin = "python3.12"; }
    { name = "py313"; bin = "python3.13"; }
    { name = "pypy3"; bin = "pypy3"; }
  ];

  testTasks = lib.listToAttrs (map
    (env: lib.nameValuePair "test:${env.name}" {
      description = "Run tests under ${env.bin}";
      exec = "${env.bin} -m unittest discover --quiet --start-directory tests --top-level-directory .";
    })
    envs);
in
{
  languages.python = {
    enable = true;
    version = "3.13";
  };

  # ------------------------------------------------------------------
  # Dev tools + test matrix interpreters
  # ------------------------------------------------------------------
  packages = [
    pkgs.black  # Also used interactively.
    pkgs.mypy
    pkgs.python3Packages.build
    pkgs.python3Packages.twine
    pkgs.pypy3  # PyPy 3.x → bin/pypy3
  ] ++ oldPythons;

  # enterShell = ''
  # '';

  # enterTest = ''
  #     Setup test environment.
  # '';

  tasks = testTasks // {
    "test:type" = {
      description = "Run type check on code base";
      exec = "mypy";
    };

    "test:all" = {
      description = "Run the full test matrix";
      after = (map (env: "test:${env.name}") envs) ++ [ "test:type" ];
      before = [ "devenv:enterTest" ];
    };

    "publish:clean" = {
      description = "Remove build artifacts (build/, dist/, *.egg-info/)";
      exec = "rm -rf build dist concurrent_iterator.egg-info";
    };

    "publish:build" = {
      description = "Build sdist and wheel distributions into dist/";
      after = [ "publish:clean" ];
      exec = "pyproject-build --sdist --wheel --outdir dist";
    };

    "publish:upload" = {
      description = "Build and upload the package to PyPI";
      after = [ "publish:build" "test:all" ];
      exec = "twine upload dist/*";
    };
  };

  # https://devenv.sh/git-hooks/
  git-hooks.hooks = {
# Standard lints and checks.
    check-added-large-files.enable = true;
    check-json.enable = true;
    check-symlinks.enable = true;
    check-toml.enable = true;
    check-xml.enable = true;
    check-yaml.enable = true;
    end-of-file-fixer.enable = true;
    mdsh.enable = true;
    pretty-format-json = {
      enable = true;
      args = [
        "--autofix"
        "--no-sort-keys"
      ];
    };
    shellcheck.enable = true;
    # Fails. trailing-whitespace.enable = true;
    yamlfmt.enable = true;

# Python.
    black.enable = true;
    isort.enable = true;
    mypy.enable = true;
  };
}
