project('vsletterbox', 'c', 'cpp',
  version: '1.0.0',
  default_options: ['c_std=c99', 'cpp_std=c++20', 'buildtype=release', 'b_ndebug=if-release', 'b_lto=true']
)

sources = [
  'vsletterboxc/vsletterbox.cpp'
]

vapoursynth = dependency('vapoursynth').partial_dependency(compile_args: true, includes: true)

py = import('python').find_installation(pure: false)

plugin = shared_library('vsletterbox', sources,
  dependencies: [vapoursynth],
  install: true,
  install_dir: py.get_install_dir(pure: false, subdir: 'vapoursynth/plugins')
)

py.install_sources(
  'vsletterbox/__init__.py',
  'vsletterbox/vsletterbox.py',
  subdir: 'vsletterbox'
)
