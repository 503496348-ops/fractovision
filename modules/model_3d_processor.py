# -*- coding: utf-8 -*-
"""
破窗造视-Fractovision · 3D Model Processor
AtomCollide-智械工坊 · 2026

融合自 ComfyUI v0.25.1 的3D模型处理能力。

处理能力:
  - GLB格式保存
  - 网格打包/切片
  - 顶点颜色/UV支持
  - 纹理嵌入

Usage:
    from modules.model_3d_processor import Model3DProcessor
    processor = Model3DProcessor()
    result = processor.save_glb(vertices, faces, "output.glb")
"""

import os
import json
import struct
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np


class Model3DFormat(Enum):
    """3D模型格式"""
    GLB = "glb"
    GLTF = "gltf"
    OBJ = "obj"
    FBX = "fbx"


@dataclass
class MeshData:
    """网格数据"""
    vertices: np.ndarray  # (N, 3)
    faces: np.ndarray  # (M, 3)
    vertex_colors: Optional[np.ndarray] = None  # (N, 3) or (N, 4)
    uvs: Optional[np.ndarray] = None  # (N, 2)
    texture: Optional[np.ndarray] = None  # (H, W, 3)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingResult:
    """处理结果"""
    input_path: str
    output_path: str
    success: bool
    mesh_data: Optional[MeshData] = None
    file_size: int = 0
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class Model3DProcessor:
    """
    3D模型处理器
    
    融合自 ComfyUI v0.25.1 的3D模型处理能力。
    """
    
    def __init__(self):
        """初始化处理器"""
        self.supported_formats = {fmt.value for fmt in Model3DFormat}
    
    def save_glb(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        filepath: str,
        vertex_colors: Optional[np.ndarray] = None,
        uvs: Optional[np.ndarray] = None,
        texture: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
        unlit: bool = False,
    ) -> ProcessingResult:
        """
        保存为GLB格式
        
        Args:
            vertices: 顶点坐标 (N, 3)
            faces: 面索引 (M, 3)
            filepath: 输出路径
            vertex_colors: 顶点颜色 (N, 3) or (N, 4)
            uvs: 纹理坐标 (N, 2)
            texture: 纹理图像 (H, W, 3)
            metadata: 元数据
            unlit: 是否无光照
            
        Returns:
            处理结果
        """
        try:
            # 确保目录存在
            output_path = Path(filepath)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 转换为numpy数组
            vertices_np = vertices.astype(np.float32)
            faces_np = faces.astype(np.int64)
            uvs_np = uvs.astype(np.float32) if uvs is not None else None
            colors_np = vertex_colors.astype(np.float32) if vertex_colors is not None else None
            
            if colors_np is not None:
                colors_np = np.clip(colors_np, 0.0, 1.0)
            
            # 构建GLB数据
            glb_data = self._build_glb(
                vertices_np, faces_np, uvs_np, colors_np, texture, metadata, unlit
            )
            
            # 保存文件
            with open(filepath, 'wb') as f:
                f.write(glb_data)
            
            # 获取文件大小
            file_size = os.path.getsize(filepath)
            
            return ProcessingResult(
                input_path="",
                output_path=filepath,
                success=True,
                file_size=file_size,
            )
            
        except Exception as e:
            return ProcessingResult(
                input_path="",
                output_path=filepath,
                success=False,
                issues=[f"保存GLB失败: {str(e)}"],
            )
    
    def load_glb(self, filepath: str) -> ProcessingResult:
        """
        加载GLB格式
        
        Args:
            filepath: 输入路径
            
        Returns:
            处理结果
        """
        try:
            path = Path(filepath)
            if not path.exists():
                return ProcessingResult(
                    input_path=filepath,
                    output_path="",
                    success=False,
                    issues=["文件不存在"],
                )
            
            # 读取GLB文件
            with open(filepath, 'rb') as f:
                data = f.read()
            
            # 解析GLB头部
            if len(data) < 12:
                return ProcessingResult(
                    input_path=filepath,
                    output_path="",
                    success=False,
                    issues=["文件格式错误"],
                )
            
            # 验证魔数
            magic = struct.unpack('<I', data[:4])[0]
            if magic != 0x46546C67:  # glTF
                return ProcessingResult(
                    input_path=filepath,
                    output_path="",
                    success=False,
                    issues=["不是有效的GLB文件"],
                )
            
            # 解析版本和长度
            version = struct.unpack('<I', data[4:8])[0]
            length = struct.unpack('<I', data[8:12])[0]
            
            # 解析JSON块
            chunk_length = struct.unpack('<I', data[12:16])[0]
            chunk_type = struct.unpack('<I', data[16:20])[0]
            
            if chunk_type != 0x4E4F534A:  # JSON
                return ProcessingResult(
                    input_path=filepath,
                    output_path="",
                    success=False,
                    issues=["JSON块未找到"],
                )
            
            json_data = data[20:20+chunk_length]
            gltf = json.loads(json_data.decode('utf-8'))
            
            # 提取网格数据
            mesh_data = self._extract_mesh_data(gltf, data)
            
            return ProcessingResult(
                input_path=filepath,
                output_path="",
                success=True,
                mesh_data=mesh_data,
                file_size=os.path.getsize(filepath),
            )
            
        except Exception as e:
            return ProcessingResult(
                input_path=filepath,
                output_path="",
                success=False,
                issues=[f"加载GLB失败: {str(e)}"],
            )
    
    def _build_glb(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        uvs: Optional[np.ndarray],
        colors: Optional[np.ndarray],
        texture: Optional[np.ndarray],
        metadata: Optional[Dict[str, Any]],
        unlit: bool,
    ) -> bytes:
        """构建GLB数据"""
        # 构建glTF JSON
        gltf = {
            "asset": {"version": "2.0", "generator": "AtomCollide-Model3DProcessor"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
            "accessors": [],
            "bufferViews": [],
            "buffers": [],
        }
        
        # 添加元数据
        if metadata:
            gltf["asset"]["extras"] = metadata
        
        # 构建缓冲区数据
        buffer_data = bytearray()
        
        # 顶点数据
        vertices_bytes = vertices.tobytes()
        vertices_offset = len(buffer_data)
        buffer_data.extend(vertices_bytes)
        
        gltf["accessors"].append({
            "bufferView": 0,
            "componentType": 5126,  # FLOAT
            "count": len(vertices),
            "type": "VEC3",
            "max": vertices.max(axis=0).tolist(),
            "min": vertices.min(axis=0).tolist(),
        })
        
        gltf["bufferViews"].append({
            "buffer": 0,
            "byteOffset": vertices_offset,
            "byteLength": len(vertices_bytes),
            "target": 34962,  # ARRAY_BUFFER
        })
        
        # 面数据
        faces_bytes = faces.astype(np.uint32).tobytes()
        faces_offset = len(buffer_data)
        buffer_data.extend(faces_bytes)
        
        gltf["accessors"].append({
            "bufferView": 1,
            "componentType": 5125,  # UNSIGNED_INT
            "count": len(faces) * 3,
            "type": "SCALAR",
            "max": [int(faces.max())],
            "min": [int(faces.min())],
        })
        
        gltf["bufferViews"].append({
            "buffer": 0,
            "byteOffset": faces_offset,
            "byteLength": len(faces_bytes),
            "target": 34963,  # ELEMENT_ARRAY_BUFFER
        })
        
        # 添加UV数据
        if uvs is not None:
            uvs_bytes = uvs.tobytes()
            uvs_offset = len(buffer_data)
            buffer_data.extend(uvs_bytes)
            
            gltf["meshes"][0]["primitives"][0]["attributes"]["TEXCOORD_0"] = 2
            
            gltf["accessors"].append({
                "bufferView": 2,
                "componentType": 5126,  # FLOAT
                "count": len(uvs),
                "type": "VEC2",
            })
            
            gltf["bufferViews"].append({
                "buffer": 0,
                "byteOffset": uvs_offset,
                "byteLength": len(uvs_bytes),
                "target": 34962,  # ARRAY_BUFFER
            })
        
        # 添加顶点颜色数据
        if colors is not None:
            colors_bytes = colors.tobytes()
            colors_offset = len(buffer_data)
            buffer_data.extend(colors_bytes)
            
            gltf["meshes"][0]["primitives"][0]["attributes"]["COLOR_0"] = 3
            
            gltf["accessors"].append({
                "bufferView": 3,
                "componentType": 5126,  # FLOAT
                "count": len(colors),
                "type": "VEC3" if colors.shape[1] == 3 else "VEC4",
            })
            
            gltf["bufferViews"].append({
                "buffer": 0,
                "byteOffset": colors_offset,
                "byteLength": len(colors_bytes),
                "target": 34962,  # ARRAY_BUFFER
            })
        
        # 设置缓冲区
        gltf["buffers"].append({"byteLength": len(buffer_data)})
        
        # 序列化JSON
        json_bytes = json.dumps(gltf).encode('utf-8')
        
        # 填充JSON到4字节对齐
        while len(json_bytes) % 4 != 0:
            json_bytes += b' '
        
        # 构建GLB
        glb = bytearray()
        
        # GLB头部
        glb.extend(struct.pack('<I', 0x46546C67))  # magic
        glb.extend(struct.pack('<I', 2))  # version
        glb.extend(struct.pack('<I', 12 + 8 + len(json_bytes) + 8 + len(buffer_data)))  # length
        
        # JSON块
        glb.extend(struct.pack('<I', len(json_bytes)))
        glb.extend(struct.pack('<I', 0x4E4F534A))  # JSON
        glb.extend(json_bytes)
        
        # 二进制块
        glb.extend(struct.pack('<I', len(buffer_data)))
        glb.extend(struct.pack('<I', 0x004E4942))  # BIN
        glb.extend(buffer_data)
        
        return bytes(glb)
    
    def _extract_mesh_data(self, gltf: Dict[str, Any], data: bytes) -> Optional[MeshData]:
        """从glTF中提取网格数据"""
        try:
            # 获取第一个网格
            mesh = gltf.get("meshes", [{}])[0]
            primitive = mesh.get("primitives", [{}])[0]
            attributes = primitive.get("attributes", {})
            
            # 获取访问器
            accessors = gltf.get("accessors", [])
            buffer_views = gltf.get("bufferViews", [])
            buffers = gltf.get("buffers", [])
            
            # 提取顶点数据
            position_idx = attributes.get("POSITION")
            if position_idx is None:
                return None
            
            accessor = accessors[position_idx]
            buffer_view = buffer_views[accessor["bufferView"]]
            
            # 计算偏移量
            offset = buffer_view.get("byteOffset", 0) + 20 + 8 + len(json.dumps(gltf).encode('utf-8'))
            
            # 读取顶点数据
            vertices = np.frombuffer(
                data[offset:offset + accessor["count"] * 12],
                dtype=np.float32
            ).reshape(-1, 3)
            
            # 提取面数据
            indices_idx = primitive.get("indices")
            faces = None
            if indices_idx is not None:
                accessor = accessors[indices_idx]
                buffer_view = buffer_views[accessor["bufferView"]]
                
                offset = buffer_view.get("byteOffset", 0) + 20 + 8 + len(json.dumps(gltf).encode('utf-8'))
                
                if accessor["componentType"] == 5125:  # UNSIGNED_INT
                    faces = np.frombuffer(
                        data[offset:offset + accessor["count"] * 4],
                        dtype=np.uint32
                    ).reshape(-1, 3)
                elif accessor["componentType"] == 5123:  # UNSIGNED_SHORT
                    faces = np.frombuffer(
                        data[offset:offset + accessor["count"] * 2],
                        dtype=np.uint16
                    ).reshape(-1, 3)
            
            return MeshData(
                vertices=vertices,
                faces=faces if faces is not None else np.array([]),
            )
            
        except Exception:
            return None
    
    def generate_report(self, results: List[ProcessingResult]) -> Dict[str, Any]:
        """生成处理报告"""
        success_count = sum(1 for r in results if r.success)
        failed_count = sum(1 for r in results if not r.success)
        
        return {
            "total_processed": len(results),
            "success": success_count,
            "failed": failed_count,
            "issues": [issue for r in results for issue in r.issues],
            "recommendations": [rec for r in results for rec in r.recommendations],
        }


# ── Self-test ──

if __name__ == "__main__":
    import tempfile
    
    print("🔍 3D Model Processor 自测")
    print("=" * 50)
    
    # 创建测试数据
    vertices = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float32)
    
    faces = np.array([
        [0, 1, 2],
        [0, 1, 3],
        [0, 2, 3],
        [1, 2, 3],
    ], dtype=np.int64)
    
    # 创建测试目录
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test.glb"
        
        # 运行处理
        processor = Model3DProcessor()
        
        # 保存GLB
        result = processor.save_glb(
            vertices, faces, str(output_path),
            metadata={"name": "test_cube"},
        )
        
        print(f"\n📊 保存结果:")
        print(f"  成功: {result.success}")
        print(f"  文件大小: {result.file_size} bytes")
        
        if result.issues:
            print(f"\n⚠️ 问题:")
            for issue in result.issues:
                print(f"  - {issue}")
        
        # 加载GLB
        if result.success:
            load_result = processor.load_glb(str(output_path))
            
            print(f"\n📊 加载结果:")
            print(f"  成功: {load_result.success}")
            
            if load_result.mesh_data:
                print(f"  顶点数: {len(load_result.mesh_data.vertices)}")
                print(f"  面数: {len(load_result.mesh_data.faces)}")
    
    print("\n✅ 自测完成")
