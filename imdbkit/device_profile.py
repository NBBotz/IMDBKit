import json
import random
import time
import uuid
import zlib
from .security import aes_encrypt


def encode_with_crc(obj):
    payload = json.dumps(obj, separators=(',', ':')).encode('utf-8')
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    hex_crc = f"{crc:08x}"
    checksum = hex_crc.encode('ascii').upper()
    return checksum, checksum + b"#" + payload

webgl = '''[
  {
    "webgl_unmasked_renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M2 Pro, Unspecified Version)",
    "webgl": [
      {
        "webgl_extensions": "ANGLE_instanced_arrays;EXT_blend_minmax;EXT_clip_control;EXT_color_buffer_half_float;EXT_depth_clamp;EXT_disjoint_timer_query;EXT_float_blend;EXT_frag_depth;EXT_polygon_offset_clamp;EXT_shader_texture_lod;EXT_texture_compression_bptc;EXT_texture_compression_rgtc;EXT_texture_filter_anisotropic;EXT_texture_mirror_clamp_to_edge;EXT_sRGB;KHR_parallel_shader_compile;OES_element_index_uint;OES_fbo_render_mipmap;OES_standard_derivatives;OES_texture_float;OES_texture_float_linear;OES_texture_half_float;OES_texture_half_float_linear;OES_vertex_array_object;WEBGL_blend_func_extended;WEBGL_color_buffer_float;WEBGL_compressed_texture_astc;WEBGL_compressed_texture_etc;WEBGL_compressed_texture_etc1;WEBGL_compressed_texture_pvrtc;WEBGL_compressed_texture_s3tc;WEBGL_compressed_texture_s3tc_srgb;WEBGL_debug_renderer_info;WEBGL_debug_shaders;WEBGL_depth_texture;WEBGL_draw_buffers;WEBGL_lose_context;WEBGL_multi_draw;WEBGL_polygon_mode",
        "webgl_extensions_hash": "9cbeeda2b4ce5415b07e1d1e43783a58",
        "webgl_renderer": "WebKit WebGL",
        "webgl_vendor": "WebKit",
        "webgl_version": "WebGL 1.0 (OpenGL ES 2.0 Chromium)",
        "webgl_shading_language_version": "WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)",
        "webgl_aliased_line_width_range": "[1, 1]",
        "webgl_aliased_point_size_range": "[1, 511]",
        "webgl_antialiasing": true,
        "webgl_bits": "8,8,24,8,8,0",
        "webgl_max_params": "16,32,16384,1024,16384,16,16,30,16,16,1024",
        "webgl_max_viewport_dims": "[16384, 16384]",
        "webgl_unmasked_vendor": "Google Inc. (Apple)",
        "webgl_unmasked_renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M2 Pro, Unspecified Version)",
        "webgl_vsf_params": "23,127,127,23,127,127,23,127,127",
        "webgl_vsi_params": "0,31,30,0,31,30,0,31,30",
        "webgl_fsf_params": "23,127,127,23,127,127,23,127,127",
        "webgl_fsi_params": "0,31,30,0,31,30,0,31,30",
        "webgl_hash_webgl": "a5c294663e62715a685b8a5f7d436da2"
      }
    ]
  },
  {
    "webgl_unmasked_renderer": "ANGLE (AMD, AMD Radeon(TM) Graphics (0x00001681) Direct3D11 vs_5_0 ps_5_0, D3D11)",
    "webgl": [
      {
        "webgl_extensions": "ANGLE_instanced_arrays;EXT_blend_minmax;EXT_clip_control;EXT_color_buffer_half_float;EXT_depth_clamp;EXT_disjoint_timer_query;EXT_float_blend;EXT_frag_depth;EXT_polygon_offset_clamp;EXT_shader_texture_lod;EXT_texture_compression_bptc;EXT_texture_compression_rgtc;EXT_texture_filter_anisotropic;EXT_texture_mirror_clamp_to_edge;EXT_sRGB;KHR_parallel_shader_compile;OES_element_index_uint;OES_fbo_render_mipmap;OES_standard_derivatives;OES_texture_float;OES_texture_float_linear;OES_texture_half_float;OES_texture_half_float_linear;OES_vertex_array_object;WEBGL_blend_func_extended;WEBGL_color_buffer_float;WEBGL_compressed_texture_s3tc;WEBGL_compressed_texture_s3tc_srgb;WEBGL_debug_renderer_info;WEBGL_debug_shaders;WEBGL_depth_texture;WEBGL_draw_buffers;WEBGL_lose_context;WEBGL_multi_draw;WEBGL_polygon_mode",
        "webgl_extensions_hash": "7300c23f4e6fa34e534fc99c1b628588",
        "webgl_renderer": "WebKit WebGL",
        "webgl_vendor": "WebKit",
        "webgl_version": "WebGL 1.0 (OpenGL ES 2.0 Chromium)",
        "webgl_shading_language_version": "WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)",
        "webgl_aliased_line_width_range": "[1, 1]",
        "webgl_aliased_point_size_range": "[1, 1024]",
        "webgl_antialiasing": true,
        "webgl_bits": "8,8,24,8,8,0",
        "webgl_max_params": "16,32,16384,1024,16384,16,16,30,16,16,4096",
        "webgl_max_viewport_dims": "[32767, 32767]",
        "webgl_unmasked_vendor": "Google Inc. (AMD)",
        "webgl_unmasked_renderer": "ANGLE (AMD, AMD Radeon(TM) Graphics (0x00001681) Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "webgl_vsf_params": "23,127,127,23,127,127,23,127,127",
        "webgl_vsi_params": "0,31,30,0,31,30,0,31,30",
        "webgl_fsf_params": "23,127,127,23,127,127,23,127,127",
        "webgl_fsi_params": "0,31,30,0,31,30,0,31,30",
        "webgl_hash_webgl": "16b93cc1541b205283c1a77320ce4fc0"
      }
    ]
  },
  {
    "webgl_unmasked_renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics (0x00009A49) Direct3D11 vs_5_0 ps_5_0, D3D11)",
    "webgl": [
      {
        "webgl_extensions": "ANGLE_instanced_arrays;EXT_blend_minmax;EXT_clip_control;EXT_color_buffer_half_float;EXT_depth_clamp;EXT_disjoint_timer_query;EXT_float_blend;EXT_frag_depth;EXT_polygon_offset_clamp;EXT_shader_texture_lod;EXT_texture_compression_bptc;EXT_texture_compression_rgtc;EXT_texture_filter_anisotropic;EXT_texture_mirror_clamp_to_edge;EXT_sRGB;KHR_parallel_shader_compile;OES_element_index_uint;OES_fbo_render_mipmap;OES_standard_derivatives;OES_texture_float;OES_texture_float_linear;OES_texture_half_float;OES_texture_half_float_linear;OES_vertex_array_object;WEBGL_blend_func_extended;WEBGL_color_buffer_float;WEBGL_compressed_texture_s3tc;WEBGL_compressed_texture_s3tc_srgb;WEBGL_debug_renderer_info;WEBGL_debug_shaders;WEBGL_depth_texture;WEBGL_draw_buffers;WEBGL_lose_context;WEBGL_multi_draw;WEBGL_polygon_mode",
        "webgl_extensions_hash": "7300c23f4e6fa34e534fc99c1b628588",
        "webgl_renderer": "WebKit WebGL",
        "webgl_vendor": "WebKit",
        "webgl_version": "WebGL 1.0 (OpenGL ES 2.0 Chromium)",
        "webgl_shading_language_version": "WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)",
        "webgl_aliased_line_width_range": "[1, 1]",
        "webgl_aliased_point_size_range": "[1, 1024]",
        "webgl_antialiasing": true,
        "webgl_bits": "8,8,24,8,8,0",
        "webgl_max_params": "16,32,16384,1024,16384,16,16,30,16,16,4096",
        "webgl_max_viewport_dims": "[32767, 32767]",
        "webgl_unmasked_vendor": "Google Inc. (Intel)",
        "webgl_unmasked_renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics (0x00009A49) Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "webgl_vsf_params": "23,127,127,23,127,127,23,127,127",
        "webgl_vsi_params": "0,31,30,0,31,30,0,31,30",
        "webgl_fsf_params": "23,127,127,23,127,127,23,127,127",
        "webgl_fsi_params": "0,31,30,0,31,30,0,31,30",
        "webgl_hash_webgl": "d794114e20f8a75cec3b812f98a42b7e"
      }
    ]
  },
  {
    "webgl_unmasked_renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics (0x000046A6) Direct3D11 vs_5_0 ps_5_0, D3D11)",
    "webgl": [
      {
        "webgl_extensions": "ANGLE_instanced_arrays;EXT_blend_minmax;EXT_clip_control;EXT_color_buffer_half_float;EXT_depth_clamp;EXT_disjoint_timer_query;EXT_float_blend;EXT_frag_depth;EXT_polygon_offset_clamp;EXT_shader_texture_lod;EXT_texture_compression_bptc;EXT_texture_compression_rgtc;EXT_texture_filter_anisotropic;EXT_texture_mirror_clamp_to_edge;EXT_sRGB;KHR_parallel_shader_compile;OES_element_index_uint;OES_fbo_render_mipmap;OES_standard_derivatives;OES_texture_float;OES_texture_float_linear;OES_texture_half_float;OES_texture_half_float_linear;OES_vertex_array_object;WEBGL_blend_func_extended;WEBGL_color_buffer_float;WEBGL_compressed_texture_s3tc;WEBGL_compressed_texture_s3tc_srgb;WEBGL_debug_renderer_info;WEBGL_debug_shaders;WEBGL_depth_texture;WEBGL_draw_buffers;WEBGL_lose_context;WEBGL_multi_draw;WEBGL_polygon_mode",
        "webgl_extensions_hash": "7300c23f4e6fa34e534fc99c1b628588",
        "webgl_renderer": "WebKit WebGL",
        "webgl_vendor": "WebKit",
        "webgl_version": "WebGL 1.0 (OpenGL ES 2.0 Chromium)",
        "webgl_shading_language_version": "WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)",
        "webgl_aliased_line_width_range": "[1, 1]",
        "webgl_aliased_point_size_range": "[1, 1024]",
        "webgl_antialiasing": true,
        "webgl_bits": "8,8,24,8,8,0",
        "webgl_max_params": "16,32,16384,1024,16384,16,16,30,16,16,4096",
        "webgl_max_viewport_dims": "[32767, 32767]",
        "webgl_unmasked_vendor": "Google Inc. (Intel)",
        "webgl_unmasked_renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics (0x000046A6) Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "webgl_vsf_params": "23,127,127,23,127,127,23,127,127",
        "webgl_vsi_params": "0,31,30,0,31,30,0,31,30",
        "webgl_fsf_params": "23,127,127,23,127,127,23,127,127",
        "webgl_fsi_params": "0,31,30,0,31,30,0,31,30",
        "webgl_hash_webgl": "134cccc7e07355b85e9546597e143227"
      }
    ]
  },
  {
    "webgl_unmasked_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    "webgl": [
      {
        "webgl_extensions": "ANGLE_instanced_arrays;EXT_blend_minmax;EXT_clip_control;EXT_color_buffer_half_float;EXT_depth_clamp;EXT_disjoint_timer_query;EXT_float_blend;EXT_frag_depth;EXT_polygon_offset_clamp;EXT_shader_texture_lod;EXT_texture_compression_bptc;EXT_texture_compression_rgtc;EXT_texture_filter_anisotropic;EXT_texture_mirror_clamp_to_edge;EXT_sRGB;KHR_parallel_shader_compile;OES_element_index_uint;OES_fbo_render_mipmap;OES_standard_derivatives;OES_texture_float;OES_texture_float_linear;OES_texture_half_float;OES_texture_half_float_linear;OES_vertex_array_object;WEBGL_blend_func_extended;WEBGL_color_buffer_float;WEBGL_compressed_texture_s3tc;WEBGL_compressed_texture_s3tc_srgb;WEBGL_debug_renderer_info;WEBGL_debug_shaders;WEBGL_depth_texture;WEBGL_draw_buffers;WEBGL_lose_context;WEBGL_multi_draw;WEBGL_polygon_mode",
        "webgl_extensions_hash": "7300c23f4e6fa34e534fc99c1b628588",
        "webgl_renderer": "WebKit WebGL",
        "webgl_vendor": "WebKit",
        "webgl_version": "WebGL 1.0 (OpenGL ES 2.0 Chromium)",
        "webgl_shading_language_version": "WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)",
        "webgl_aliased_line_width_range": "[1, 1]",
        "webgl_aliased_point_size_range": "[1, 1024]",
        "webgl_antialiasing": true,
        "webgl_bits": "8,8,24,8,8,0",
        "webgl_max_params": "16,32,16384,1024,16384,16,16,30,16,16,4096",
        "webgl_max_viewport_dims": "[32767, 32767]",
        "webgl_unmasked_vendor": "Google Inc. (NVIDIA)",
        "webgl_unmasked_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "webgl_vsf_params": "23,127,127,23,127,127,23,127,127",
        "webgl_vsi_params": "0,31,30,0,31,30,0,31,30",
        "webgl_fsf_params": "23,127,127,23,127,127,23,127,127",
        "webgl_fsi_params": "0,31,30,0,31,30,0,31,30",
        "webgl_hash_webgl": "9f0515f4e1564700d4187a552179a6d0"
      }
    ]
  },
  {
    "webgl_unmasked_renderer": "ANGLE (Apple, Apple M1, OpenGL 4.1 Metal - 76.3)",
    "webgl": [
      {
        "webgl_extensions": "ANGLE_instanced_arrays;EXT_blend_minmax;EXT_clip_control;EXT_color_buffer_half_float;EXT_depth_clamp;EXT_disjoint_timer_query;EXT_float_blend;EXT_frag_depth;EXT_polygon_offset_clamp;EXT_shader_texture_lod;EXT_texture_compression_bptc;EXT_texture_compression_rgtc;EXT_texture_filter_anisotropic;EXT_texture_mirror_clamp_to_edge;EXT_sRGB;KHR_parallel_shader_compile;OES_element_index_uint;OES_fbo_render_mipmap;OES_standard_derivatives;OES_texture_float;OES_texture_float_linear;OES_texture_half_float;OES_texture_half_float_linear;OES_vertex_array_object;WEBGL_blend_func_extended;WEBGL_color_buffer_float;WEBGL_compressed_texture_astc;WEBGL_compressed_texture_etc;WEBGL_compressed_texture_etc1;WEBGL_compressed_texture_pvrtc;WEBGL_compressed_texture_s3tc;WEBGL_compressed_texture_s3tc_srgb;WEBGL_debug_renderer_info;WEBGL_debug_shaders;WEBGL_depth_texture;WEBGL_draw_buffers;WEBGL_lose_context;WEBGL_multi_draw;WEBGL_polygon_mode",
        "webgl_extensions_hash": "9cbeeda2b4ce5415b07e1d1e43783a58",
        "webgl_renderer": "WebKit WebGL",
        "webgl_vendor": "WebKit",
        "webgl_version": "WebGL 1.0 (OpenGL ES 2.0 Chromium)",
        "webgl_shading_language_version": "WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)",
        "webgl_aliased_line_width_range": "[1, 1]",
        "webgl_aliased_point_size_range": "[1, 511]",
        "webgl_antialiasing": true,
        "webgl_bits": "8,8,24,8,8,0",
        "webgl_max_params": "16,32,16384,1024,16384,16,16,30,16,16,1024",
        "webgl_max_viewport_dims": "[16384, 16384]",
        "webgl_unmasked_vendor": "Apple Inc.",
        "webgl_unmasked_renderer": "Apple M1",
        "webgl_vsf_params": "23,127,127,23,127,127,23,127,127",
        "webgl_vsi_params": "0,31,30,0,31,30,0,31,30",
        "webgl_fsf_params": "23,127,127,23,127,127,23,127,127",
        "webgl_fsi_params": "0,31,30,0,31,30,0,31,30",
        "webgl_hash_webgl": "3887d7b30f81d830b80988771415123d"
      }
    ]
  }
]'''

gpus = json.loads(webgl)

def create_fingerprint(user_agent: str):
    ts = int(time.time() * 1000)

    if "Windows" in user_agent:
        candidates = [g for g in gpus if "Direct3D11" in g["webgl_unmasked_renderer"]]
    elif "Mac" in user_agent:
        candidates = [g for g in gpus if "Apple" in g["webgl_unmasked_renderer"]]
    else:
        candidates = gpus

    gpu = random.choice(candidates or gpus)

    bins = [random.randrange(0,40) for _ in range(256)]
    bins[0], bins[-1] = random.randrange(14473, 16573), random.randrange(14473, 16573)

    fp = {
        "metrics": {"fp2": 1, "browser": 0, "capabilities": 1, "gpu": 7, "dnt": 0, "math": 0, "screen": 0,
                    "navigator": 0, "auto": 1, "stealth": 0, "subtle": 0, "canvas": 5, "formdetector": 1, "be": 0},
        "start": ts,
        "flashVersion": None,
        "plugins": [{"name": "PDF Viewer", "str": "PDF Viewer "},
                    {"name": "Chrome PDF Viewer", "str": "Chrome PDF Viewer "},
                    {"name": "Chromium PDF Viewer", "str": "Chromium PDF Viewer "},
                    {"name": "Microsoft Edge PDF Viewer", "str": "Microsoft Edge PDF Viewer "},
                    {"name": "WebKit built-in PDF", "str": "WebKit built-in PDF "}],
        "dupedPlugins": "PDF Viewer Chrome PDF Viewer Chromium PDF Viewer Microsoft Edge PDF Viewer WebKit built-in PDF ||1920-1080-1032-24-*-*-*",
        "screenInfo": "1920-1080-1032-24-*-*-*",
        "referrer": "",
        "userAgent": user_agent,
        "location": "", # they probably don't check this
        "webDriver": False,
        "capabilities": {
            "css": {
                "textShadow": 1,
                "WebkitTextStroke": 1,
                "boxShadow": 1,
                "borderRadius": 1,
                "borderImage": 1,
                "opacity": 1,
                "transform": 1,
                "transition": 1
            },
            "js": {
                "audio": True,
                "geolocation": random.choice([True, False]),
                "localStorage": "supported",
                "touch": False,
                "video": True,
                "webWorker": random.choice([True, False]),
            },
            "elapsed": 1
        },
        "gpu": {
            "vendor": gpu["webgl"][0]["webgl_unmasked_vendor"],
            "model": gpu["webgl_unmasked_renderer"],
            "extensions": gpu["webgl"][0]["webgl_extensions"].split(";")
        },
        "dnt": None,
        "math": {
            "tan": "-1.4214488238747245",
            "sin": "0.8178819121159085",
            "cos": "-0.5753861119575491"
        },
        "automation": {
            "wd": {
                "properties": {
                    "document": [],
                    "window": [],
                    "navigator": []
                }
            },
            "phantom": {
                "properties": {
                    "window": []
                }
            }
        },
        "stealth": {
            "t1": 0,
            "t2": 0,
            "i": 1,
            "mte": 0,
            "mtd": False
        },
        "crypto": {
            "crypto": 1,
            "subtle": 1,
            "encrypt": True,
            "decrypt": True,
            "wrapKey": True,
            "unwrapKey": True,
            "sign": True,
            "verify": True,
            "digest": True,
            "deriveBits": True,
            "deriveKey": True,
            "getRandomValues": True,
            "randomUUID": True
        },
        "canvas": {
            "hash": random.randrange(645172295, 735192295),
            "emailHash": None,
            "histogramBins": bins
        },
        "formDetected": False,
        "numForms": 0,
        "numFormElements": 0,
        "be": {
            "si": False
        },
        "end": ts + 1,
        "errors": [],
        "version": "2.4.0",
        "id": str(uuid.uuid4()),
    }
    checksum, data = encode_with_crc(fp)
    return checksum.decode(), aes_encrypt(data)
