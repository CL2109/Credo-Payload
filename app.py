import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item

# --- 1. OVERRIDE ITEM TO PREVENT ROTATION ---
class StrictItem(Item):
    """
    Overrides the standard py3dbp Item to prevent rotation.
    When the algorithm tests a rotated state, this returns 
    impossibly large dimensions, forcing it to only use rotation 0.
    """
    def get_dimension(self):
        if getattr(self, 'rotation_type', 0) != 0:
            return [999999, 999999, 999999]
        return [self.width, self.height, self.depth]

    def getDimension(self):
        # Compatibility fallback for older versions of py3dbp
        return self.get_dimension()

# --- 2. CREDO DATABASE ---
CREDO_BOXES = {
    "Credo 4L": (143, 143, 137),
    "Credo 12L": (222, 222, 216),
    "Credo 28L": (298, 292, 292),
    "Credo 56L": (375, 375, 369),
    "Credo 96L": (451, 451, 445),
    "Credo Half Stack": (1027, 825, 438),
    "Credo Full Stack": (1027, 825, 953)
}

def create_box_mesh(x, y, z, dx, dy, dz, color, name):
    xp = [x, x+dx, x+dx, x, x, x+dx, x+dx, x]
    yp = [y, y, y+dy, y+dy, y, y, y+dy, y+dy]
    zp = [z, z, z, z, z+dz, z+dz, z+dz, z+dz]
    i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
    return go.Mesh3d(
        x=xp, y=yp, z=zp, i=i, j=j, k=k,
        color=color, opacity=0.6, name=name, showlegend=True,
        hovertemplate=f"<b>{name}</b><br>Dims: {dx}x{dy}x{dz}<br>Pos: ({x},{y},{z})<extra></extra>"
    )

st.set_page_config(page_title="Credo 3D Load Planner", layout="wide")
st.title("📦 Credo 3D Load Planner")

st.sidebar.header("1. Select Container")
selected_box = st.sidebar.selectbox("Choose a Credo Box", list(CREDO_BOXES.keys()))
box_dims = CREDO_BOXES[selected_box]
st.sidebar.write(f"**Payload Dims:** {box_dims[0]} x {box_dims[1]} x {box_dims[2]} mm")

st.header("2. Add Products")
st.write("Enter your products. Check 'Strict Orientation' if the box must stay upright (no rotating).")

# Added boolean column for strict orientation
if "product_data" not in st.session_state:
    st.session_state.product_data = pd.DataFrame({
        "Product Name": ["Vial Box A", "Syringe Box B"],
        "Length (mm)": [100, 120],
        "Width (mm)": [50, 80],
        "Height (mm)": [50, 40],
        "Quantity": [5, 3],
        "Strict Orientation": [True, False]
    })

# Render the editable grid (Streamlit will automatically turn the boolean column into checkboxes)
edited_df = st.data_editor(
    st.session_state.product_data, 
    num_rows="dynamic", 
    use_container_width=True
)

if st.button("Calculate Load & Generate 3D Model", type="primary"):
    packer = Packer()
    packer.add_bin(Bin(selected_box, box_dims[0], box_dims[1], box_dims[2], 10000))
    
    for index, row in edited_df.iterrows():
        if pd.notna(row["Product Name"]) and pd.notna(row["Quantity"]) and pd.notna(row["Length (mm)"]):
            try:
                qty = int(row["Quantity"])
                is_strict = bool(row.get("Strict Orientation", False))
                
                if qty > 0:
                    for i in range(qty):
                        item_name = f"{row['Product Name']} ({i+1})"
                        
                        # Apply the StrictItem class if the checkbox is ticked
                        if is_strict:
                            packer.add_item(StrictItem(item_name, float(row["Length (mm)"]), float(row["Width (mm)"]), float(row["Height (mm)"]), 1))
                        else:
                            packer.add_item(Item(item_name, float(row["Length (mm)"]), float(row["Width (mm)"]), float(row["Height (mm)"]), 1))
            except (ValueError, TypeError):
                pass
                
    packer.pack()
    b = packer.bins[0]
    
    st.subheader(f"Packing Results for {b.name}")
    
    fig = go.Figure()
    fig.add_trace(create_box_mesh(0, 0, 0, b.width, b.height, b.depth, "rgba(200, 200, 200, 0.1)", "Credo Box Container"))
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
    product_colors = {}
    
    for item in b.items:
        base_name = item.name.split(" (")[0]
        if base_name not in product_colors:
            product_colors[base_name] = colors[len(product_colors) % len(colors)]
            
        x, y, z = [float(i) for i in item.position]
        dx, dy, dz = float(item.width), float(item.height), float(item.depth)
        fig.add_trace(create_box_mesh(x, y, z, dx, dy, dz, product_colors[base_name], base_name))
        
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Length', range=[0, b.width]),
            yaxis=dict(title='Width', range=[0, b.height]),
            zaxis=dict(title='Height', range=[0, b.depth]),
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=0),
        height=600
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    if b.unfitted_items:
        st.error(f"⚠️ {len(b.unfitted_items)} item(s) did NOT fit!")
        unfitted_names = [item.name for item in b.unfitted_items]
        st.write(", ".join(unfitted_names))
    else:
        st.success("✅ All items fit perfectly!")
