"""
Meeting AI Assistant - Staff Management 페이지 렌더링
"""
import streamlit as st

def render_staff_management(service_manager):
    """인사정보 관리 페이지 렌더링"""
    with st.container():
        st.markdown("# 👥 Staff Management")
        st.markdown("---")
        
        # 초기화 버튼
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("🔄 더미 데이터 초기화"):
                try:
                    service_manager.init_staff_data()
                    st.success("✅ 인사정보 더미 데이터가 초기화되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 초기화 오류: {str(e)}")
        
        with col2:
            if st.button("➕ 새 직원 추가"):
                st.session_state.show_add_staff = True
        
        # 새 직원 추가 폼
        if getattr(st.session_state, 'show_add_staff', False):
            with st.expander("➕ 새 직원 정보 입력", expanded=True):
                with st.form("add_staff_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        name = st.text_input("이름 *", placeholder="홍길동")
                        department = st.selectbox("부서 *", ["개발팀", "기획팀", "디자인팀", "마케팅팀", "기타"])
                        position = st.text_input("직책 *", placeholder="시니어 개발자")
                    
                    with col2:
                        email = st.text_input("이메일 *", placeholder="hong@company.com")
                        skills_input = st.text_area("스킬 (쉼표로 구분)", placeholder="Python, JavaScript, React")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        submitted = st.form_submit_button("👤 직원 추가", use_container_width=True)
                    with col2:
                        if st.form_submit_button("❌ 취소", use_container_width=True):
                            st.session_state.show_add_staff = False
                            st.rerun()
                    
                    if submitted:
                        if name and department and position and email:
                            skills = [skill.strip() for skill in skills_input.split(',') if skill.strip()]
                            staff_data = {
                                'name': name,
                                'department': department,
                                'position': position,
                                'email': email,
                                'skills': skills
                            }
                            
                            try:
                                new_staff_id = service_manager.add_staff(staff_data)
                                if new_staff_id:
                                    st.success(f"✅ 직원 '{name}'이 추가되었습니다!")
                                    st.session_state.show_add_staff = False
                                    st.rerun()
                                else:
                                    st.error("❌ 직원 추가에 실패했습니다.")
                            except Exception as e:
                                st.error(f"❌ 오류: {str(e)}")
                        else:
                            st.error("❌ 필수 항목을 모두 입력해주세요.")
        
        # 기존 직원 목록 표시
        try:
            staff_list = service_manager.get_all_staff()
            
            if staff_list:
                st.markdown("### 📋 직원 목록")
                
                # 검색 기능
                search_term = st.text_input("🔍 직원 검색", placeholder="이름, 부서, 직책으로 검색...")
                
                # 필터링
                if search_term:
                    filtered_staff = [
                        staff for staff in staff_list 
                        if search_term.lower() in staff.get('name', '').lower() or
                           search_term.lower() in staff.get('department', '').lower() or
                           search_term.lower() in staff.get('position', '').lower()
                    ]
                else:
                    filtered_staff = staff_list
                
                # 직원 목록 표시
                for i, staff in enumerate(filtered_staff):
                    with st.container():
                        col1, col2, col3 = st.columns([3, 2, 1])
                        
                        with col1:
                            st.markdown(f"**👤 {staff.get('name', 'N/A')}**")
                            st.caption(f"📧 {staff.get('email', 'N/A')}")
                            
                            # 스킬 태그 표시
                            skills = staff.get('skills', [])
                            if skills:
                                skills_text = " ".join([f"`{skill}`" for skill in skills[:3]])
                                if len(skills) > 3:
                                    skills_text += f" +{len(skills)-3}개"
                                st.caption(f"💡 {skills_text}")
                        
                        with col2:
                            st.info(f"🏢 {staff.get('department', 'N/A')}")
                            st.caption(f"🎯 {staff.get('position', 'N/A')}")
                        
                        with col3:
                            # 수정 버튼
                            if st.button("✏️ 수정", key=f"edit_{staff.get('id', i)}"):
                                st.session_state.edit_staff_id = staff.get('id')
                                st.session_state.edit_staff_data = staff
                            
                            # 삭제 버튼
                            if st.button("🗑️ 삭제", key=f"delete_{staff.get('id', i)}"):
                                if st.session_state.get(f"confirm_delete_{staff.get('id')}", False):
                                    try:
                                        if service_manager.delete_staff(staff.get('id')):
                                            st.success(f"✅ '{staff.get('name')}'이 삭제되었습니다!")
                                            st.rerun()
                                        else:
                                            st.error("❌ 삭제에 실패했습니다.")
                                    except Exception as e:
                                        st.error(f"❌ 오류: {str(e)}")
                                else:
                                    st.session_state[f"confirm_delete_{staff.get('id')}"] = True
                                    st.warning("⚠️ 다시 클릭하면 삭제됩니다!")
                        
                        st.markdown("---")
                
                # 수정 폼
                if hasattr(st.session_state, 'edit_staff_id') and st.session_state.edit_staff_id:
                    edit_staff = st.session_state.edit_staff_data
                    
                    with st.expander(f"✏️ '{edit_staff.get('name')}' 정보 수정", expanded=True):
                        with st.form("edit_staff_form"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                new_name = st.text_input("이름", value=edit_staff.get('name', ''))
                                new_department = st.selectbox("부서", 
                                    ["개발팀", "기획팀", "디자인팀", "마케팅팀", "기타"],
                                    index=["개발팀", "기획팀", "디자인팀", "마케팅팀", "기타"].index(edit_staff.get('department', '기타')) if edit_staff.get('department') in ["개발팀", "기획팀", "디자인팀", "마케팅팀", "기타"] else 4
                                )
                                new_position = st.text_input("직책", value=edit_staff.get('position', ''))
                            
                            with col2:
                                new_email = st.text_input("이메일", value=edit_staff.get('email', ''))
                                current_skills = ', '.join(edit_staff.get('skills', []))
                                new_skills_input = st.text_area("스킬 (쉼표로 구분)", value=current_skills)
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("✅ 수정 완료", use_container_width=True):
                                    if new_name and new_department and new_position and new_email:
                                        new_skills = [skill.strip() for skill in new_skills_input.split(',') if skill.strip()]
                                        updates = {
                                            'name': new_name,
                                            'department': new_department,
                                            'position': new_position,
                                            'email': new_email,
                                            'skills': new_skills
                                        }
                                        
                                        try:
                                            if service_manager.update_staff(st.session_state.edit_staff_id, updates):
                                                st.success(f"✅ '{new_name}' 정보가 수정되었습니다!")
                                                del st.session_state.edit_staff_id
                                                del st.session_state.edit_staff_data
                                                st.rerun()
                                            else:
                                                st.error("❌ 수정에 실패했습니다.")
                                        except Exception as e:
                                            st.error(f"❌ 오류: {str(e)}")
                                    else:
                                        st.error("❌ 필수 항목을 모두 입력해주세요.")
                            
                            with col2:
                                if st.form_submit_button("❌ 취소", use_container_width=True):
                                    del st.session_state.edit_staff_id
                                    del st.session_state.edit_staff_data
                                    st.rerun()
                
                st.info(f"📊 총 {len(filtered_staff)}명의 직원이 등록되어 있습니다.")
                
            else:
                st.info("👥 등록된 직원이 없습니다. '더미 데이터 초기화' 버튼을 클릭하거나 새 직원을 추가해보세요.")
                
        except Exception as e:
            st.error(f"❌ 직원 목록을 불러오는 중 오류가 발생했습니다: {str(e)}")
