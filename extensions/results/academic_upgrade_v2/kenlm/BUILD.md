# Rebuild external KenLM validation on Windows

Source: https://github.com/kpu/kenlm at 4cb443e60b7bf2c0ddf3c745378f76cb59e254e5.
Boost 1.89 archive: https://archives.boost.io/release/1.89.0/source/boost_1_89_0.tar.gz.
Archive SHA-256: 9de758db755e8330a01d995b0a24d09798048400ac25c03fc5ea9be364b13c93.
Tested toolchain: CMake 4.3.3, MinGW-w64 UCRT g++ 16.1.0, Windows x64.
Every cache, temporary file, download and build artifact stays inside this repository.

Run in PowerShell from the repository root after the local Python environment is prepared:

~~~powershell
. .\setup_lokal.ps1
uv sync --group dev
$work = Join-Path (Get-Location) '.tmp\academic_upgrade_v2'
New-Item -ItemType Directory -Force -Path $work | Out-Null
git clone --depth 1 https://github.com/kpu/kenlm.git (Join-Path $work 'kenlm')
git -C (Join-Path $work 'kenlm') fetch --depth 1 origin 4cb443e60b7bf2c0ddf3c745378f76cb59e254e5
git -C (Join-Path $work 'kenlm') checkout --detach 4cb443e60b7bf2c0ddf3c745378f76cb59e254e5
$archive = Join-Path $work 'boost_1_89_0.tar.gz'
curl.exe -L --fail --output $archive https://archives.boost.io/release/1.89.0/source/boost_1_89_0.tar.gz
if ((Get-FileHash -Algorithm SHA256 $archive).Hash -ne '9DE758DB755E8330A01D995B0A24D09798048400AC25C03FC5EA9BE364B13C93') { throw 'Boost archive hash mismatch' }
tar -xzf $archive -C $work
Push-Location (Join-Path $work 'boost_1_89_0')
.\bootstrap.bat gcc
.\b2.exe -j4 --with-program_options --with-system --with-thread --with-test link=shared runtime-link=shared variant=release address-model=64 stage
Pop-Location
~~~

Boost.System 1.89 is header-only. The KenLM CMake file still requests a compiled Boost.System library; the following one-line change is confined to the ignored vendor clone. No estimator or query source changes are needed:

~~~powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; p=Path('.tmp/academic_upgrade_v2/kenlm/CMakeLists.txt'); s=p.read_text(); a='  program_options\n  system\n  thread\n'; assert s.count(a)==1; p.write_text(s.replace(a,'  program_options\n  thread\n'))"
$boost = Join-Path $work 'boost_1_89_0'
cmake -S (Join-Path $work 'kenlm') -B (Join-Path $work 'kenlm_build') -G 'MinGW Makefiles' -DCMAKE_BUILD_TYPE=Release -DCOMPILE_TESTS=OFF -DENABLE_INTERPOLATE=OFF -DBoost_NO_BOOST_CMAKE=OFF "-DBoost_DIR=$boost\stage\lib\cmake\Boost-1.89.0" "-DCMAKE_PREFIX_PATH=$boost\stage\lib\cmake" "-DBOOST_ROOT=$boost" -Wno-dev
cmake --build (Join-Path $work 'kenlm_build') --target lmplz query --parallel 4
~~~

Run each order into a fresh directory. The adapter records the source commit and local patch, binary/adapter/corpus/probe SHA-256, exact CLI arguments, ARPA, query output, per-token scores, discounts and normalization:

~~~powershell
uv run python -m extensions.experiments.kenlm_validation --lmplz .tmp/academic_upgrade_v2/kenlm_build/bin/lmplz.exe --query .tmp/academic_upgrade_v2/kenlm_build/bin/query.exe --source .tmp/academic_upgrade_v2/kenlm --dll-dir .tmp/academic_upgrade_v2/boost_1_89_0/stage/lib --order 2 --output .tmp/academic_upgrade_v2/evidence_order_2
uv run python -m extensions.experiments.kenlm_validation --lmplz .tmp/academic_upgrade_v2/kenlm_build/bin/lmplz.exe --query .tmp/academic_upgrade_v2/kenlm_build/bin/query.exe --source .tmp/academic_upgrade_v2/kenlm --dll-dir .tmp/academic_upgrade_v2/boost_1_89_0/stage/lib --order 3 --output .tmp/academic_upgrade_v2/evidence_order_3
~~~

Actual completed runs are under evidence_order_2 and evidence_order_3. The Windows query binary returned pipe error 109 on Python pipe stdin; the adapter uses file-backed stdin. No global WSL/Docker installation or service was used.
